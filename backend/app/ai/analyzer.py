"""OpenRouter-backed AI synthesis over sanitized analyzer evidence only."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.models.report import Finding, RepositorySnapshot

DEFAULT_MODEL = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_FINDINGS = 40
MAX_EVIDENCE_CHARS = 180
REQUEST_TIMEOUT = 45.0


class AIAnalysisResult(BaseModel):
    """Strict structured response expected from the model."""

    summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    architecture_insight: str = ""
    documentation_insight: str = ""
    recommendations: list[str] = Field(default_factory=list)


async def analyze_with_ai(
    snapshot: RepositorySnapshot,
    *,
    overall_score: float | None = None,
    category_scores: list[dict[str, Any]] | None = None,
) -> AIAnalysisResult | None:
    """Call OpenRouter with sanitized evidence. Return None on any failure."""
    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None

    model = (os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    payload = _build_evidence_payload(snapshot, overall_score, category_scores)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior software engineering reviewer. "
                "Respond with a single JSON object only (no markdown fences). "
                "Use only the provided evidence. Never invent files, secrets, or scores. "
                "Keys required: summary (string), strengths (string array), "
                "weaknesses (string array), architecture_insight (string), "
                "documentation_insight (string), recommendations (string array). "
                "Keep each string concise and actionable."
            ),
        },
        {
            "role": "user",
            "content": (
                "Produce a project health narrative from this sanitized evidence JSON:\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
        },
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Aayushhh87/GitHub-Project-Health-Agent",
        "X-Title": "GitHub Project Health Agent",
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not isinstance(content, str) or not content.strip():
            return None
        return _parse_ai_json(content)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError):
        return None
    except Exception:
        return None


def _build_evidence_payload(
    snapshot: RepositorySnapshot,
    overall_score: float | None,
    category_scores: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Strip raw source content; send only structured, redacted signals."""
    meta = snapshot.metadata
    findings = [_sanitize_finding(f) for f in snapshot.findings[:MAX_FINDINGS]]
    sample_paths = [
        file.path
        for file in snapshot.files
        if not file.skipped
    ][:60]

    return {
        "repository": {
            "owner": meta.owner,
            "name": meta.name,
            "description": (meta.description or "")[:300] or None,
            "default_branch": meta.default_branch,
            "language": meta.language,
            "stars": meta.stars,
            "forks": meta.forks,
            "open_issues": meta.open_issues,
            "topics": meta.topics[:20],
        },
        "statistics": {
            "total_files_found": snapshot.total_files_found,
            "files_analyzed": snapshot.files_analyzed,
            "files_skipped": snapshot.files_skipped,
            "truncated": snapshot.truncated,
        },
        "languages": dict(list(_language_items(snapshot))[:15]),
        "dependencies": {
            "has_dependency_management": snapshot.dependencies.has_dependency_management,
            "ecosystems": snapshot.dependencies.ecosystems,
            "manifests": snapshot.dependencies.manifests[:15],
            "lockfiles": snapshot.dependencies.lockfiles[:15],
            "dependency_count": snapshot.dependencies.dependency_count,
            "pinned_dependencies": snapshot.dependencies.pinned_dependencies,
            "loose_dependencies": snapshot.dependencies.loose_dependencies,
        },
        "testing": {
            "tests_detected": snapshot.testing.tests_detected,
            "test_file_count": snapshot.testing.test_file_count,
            "test_directories": snapshot.testing.test_directories[:15],
            "frameworks": snapshot.testing.frameworks,
        },
        "scores": {
            "overall_score": overall_score,
            "category_scores": category_scores or [],
        },
        "findings": findings,
        "sample_paths": sample_paths,
    }


def _language_items(snapshot: RepositorySnapshot):
    from collections import Counter

    counts = Counter(
        file.language
        for file in snapshot.files
        if not file.skipped and file.language
    )
    return sorted(counts.items())


def _sanitize_finding(finding: Finding) -> dict[str, Any]:
    evidence = [
        _redact_secrets(item)[:MAX_EVIDENCE_CHARS]
        for item in finding.evidence[:3]
    ]
    return {
        "title": finding.title[:160],
        "severity": finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
        "category": finding.category,
        "file": finding.file,
        "line": finding.line,
        "description": finding.description[:400],
        "evidence": evidence,
        "recommendation": (finding.recommendation or "")[:240] or None,
    }


_SECRETISH = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|private[_-]?key|bearer\s+)\s*[:=]?\s*\S+"
)


def _redact_secrets(text: str) -> str:
    return _SECRETISH.sub(r"\1=********", text)


def _parse_ai_json(content: str) -> AIAnalysisResult | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    try:
        return AIAnalysisResult.model_validate(
            {
                "summary": str(data.get("summary") or "").strip(),
                "strengths": _string_list(data.get("strengths")),
                "weaknesses": _string_list(data.get("weaknesses")),
                "architecture_insight": str(data.get("architecture_insight") or "").strip(),
                "documentation_insight": str(data.get("documentation_insight") or "").strip(),
                "recommendations": _string_list(data.get("recommendations")),
            }
        )
    except ValidationError:
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip()[:400])
    return result[:12]
