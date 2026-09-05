"""Tests for OpenRouter AI analyzer and graceful fallback."""

from __future__ import annotations

import asyncio
import json

import httpx

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


def test_missing_api_key_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async def _run():
        return await analyze_with_ai(_snapshot(), overall_score=80.0)

    assert asyncio.run(_run()) is None


def test_openrouter_success(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    payload = {
        "summary": "Solid foundation with room to improve tests.",
        "strengths": ["Clear README"],
        "weaknesses": ["Few tests"],
        "architecture_insight": "Layered modules.",
        "documentation_insight": "README is present.",
        "recommendations": ["Add integration tests"],
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url, headers=None, json=None):
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-key-not-real"
            assert "openrouter.ai" in url
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    async def _run():
        return await analyze_with_ai(_snapshot(), overall_score=72.5)

    result = asyncio.run(_run())
    assert isinstance(result, AIAnalysisResult)
    assert result.summary.startswith("Solid foundation")
    assert result.strengths == ["Clear README"]
    assert result.recommendations == ["Add integration tests"]


def test_http_failure_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class BoomClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("network down")

    monkeypatch.setattr(httpx, "AsyncClient", BoomClient)

    async def _run():
        return await analyze_with_ai(_snapshot())

    assert asyncio.run(_run()) is None


def test_invalid_json_returns_none(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": [{"message": {"content": "not-json"}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    async def _run():
        return await analyze_with_ai(_snapshot())

    assert asyncio.run(_run()) is None


def test_parse_ai_json_with_fences() -> None:
    raw = """```json
{"summary":"ok","strengths":[],"weaknesses":[],"architecture_insight":"","documentation_insight":"","recommendations":[]}
```"""
    parsed = _parse_ai_json(raw)
    assert parsed is not None
    assert parsed.summary == "ok"


def test_parse_ai_json_rejects_empty_summary() -> None:
    assert _parse_ai_json('{"summary":"","strengths":[]}') is None
