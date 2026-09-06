"""Tests for Gemini AI analyzer and graceful fallback."""

from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace

from app.ai.analyzer import AIAnalysisResult, analyze_with_ai, _parse_ai_json
from app.models.report import RepositoryInfo, RepositorySnapshot


def _snapshot() -> RepositorySnapshot:
    return RepositorySnapshot(
        metadata=RepositoryInfo(
            url="https://github.com/owner/repo",
            owner="owner",
            name="repo",
            description="desc",
            default_branch="main",
            stars=1,
            forks=0,
            open_issues=0,
            language="Python",
            size_kb=1,
            topics=[],
        )
    )


def _install_fake_genai(monkeypatch, *, client):
    """Install a minimal google.genai package into sys.modules for local imports."""

    types_mod = ModuleType("google.genai.types")

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    types_mod.GenerateContentConfig = GenerateContentConfig

    genai_mod = ModuleType("google.genai")
    genai_mod.Client = lambda **kwargs: client
    genai_mod.types = types_mod

    google_mod = ModuleType("google")
    google_mod.genai = genai_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)


def test_missing_api_key_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    async def _run():
        return await analyze_with_ai(_snapshot(), overall_score=80.0)

    assert asyncio.run(_run()) is None


def test_gemini_success(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")

    payload = {
        "summary": "Solid foundation with room to improve tests.",
        "strengths": ["Clear README"],
        "weaknesses": ["Few tests"],
        "architecture_insight": "Layered modules.",
        "documentation_insight": "README is present.",
        "recommendations": ["Add integration tests"],
    }

    async def fake_generate_content(*, model, contents, config):
        assert model == "gemini-2.0-flash"
        assert isinstance(contents, str)
        assert "evidence" in contents.lower()
        return SimpleNamespace(text=json.dumps(payload))

    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=fake_generate_content)
        )
    )
    _install_fake_genai(monkeypatch, client=client)

    async def _run():
        return await analyze_with_ai(_snapshot(), overall_score=72.5)

    result = asyncio.run(_run())
    assert isinstance(result, AIAnalysisResult)
    assert result.summary.startswith("Solid foundation")
    assert result.strengths == ["Clear README"]
    assert result.recommendations == ["Add integration tests"]


def test_api_failure_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def boom(*, model, contents, config):
        raise RuntimeError("network down")

    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=boom))
    )
    _install_fake_genai(monkeypatch, client=client)

    async def _run():
        return await analyze_with_ai(_snapshot())

    assert asyncio.run(_run()) is None


def test_invalid_json_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def bad_json(*, model, contents, config):
        return SimpleNamespace(text="not-json")

    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=bad_json))
    )
    _install_fake_genai(monkeypatch, client=client)

    async def _run():
        return await analyze_with_ai(_snapshot())

    assert asyncio.run(_run()) is None


def test_parse_ai_json_with_fences() -> None:
    raw = """```json
{\"summary\":\"ok\",\"strengths\":[],\"weaknesses\":[],\"architecture_insight\":\"\",\"documentation_insight\":\"\",\"recommendations\":[]}
```"""
    # Fix: use real JSON without over-escaping in the actual file - rewritten below
    raw = (
        "```json\n"
        '{"summary":"ok","strengths":[],"weaknesses":[],'
        '"architecture_insight":"","documentation_insight":"","recommendations":[]}\n'
        "```"
    )
    parsed = _parse_ai_json(raw)
    assert parsed is not None
    assert parsed.summary == "ok"


def test_parse_ai_json_rejects_empty_summary() -> None:
    assert _parse_ai_json('{"summary":"","strengths":[]}') is None
