import asyncio
import base64
import json

import httpx

from app.analyzer.repository import RepositoryAnalyzer, decode_github_text
from app.github.client import GitHubClient


def test_decode_github_text_rejects_binary_and_oversized_payloads() -> None:
    text_payload = {
        "type": "file",
        "content": base64.b64encode(b"hello").decode(),
    }
    binary_payload = {
        "type": "file",
        "content": base64.b64encode(b"hello\x00world").decode(),
    }

    assert decode_github_text(text_payload) == "hello"
    assert decode_github_text(binary_payload) is None
    assert decode_github_text(text_payload, max_size=2) is None


def test_repository_analyzer_fetches_and_filters_a_snapshot(monkeypatch) -> None:
    file_content = base64.b64encode(b"print('hello')\n").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/owner/repository":
            return httpx.Response(
                200,
                json={
                    "name": "repository",
                    "owner": {"login": "owner"},
                    "description": "Example",
                    "default_branch": "main",
                    "stargazers_count": 4,
                    "forks_count": 2,
                    "open_issues_count": 1,
                    "language": "Python",
                    "size": 10,
                    "topics": ["example"],
                },
            )
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {"path": "README.md", "type": "blob", "size": 5},
                        {"path": "src/main.py", "type": "blob", "size": 15},
                        {"path": "assets/logo.png", "type": "blob", "size": 100},
                        {"path": "src", "type": "tree"},
                    ]
                },
            )
        if request.url.path.endswith("/contents/README.md"):
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "content": base64.b64encode(b"# demo").decode(),
                },
            )
        if request.url.path.endswith("/contents/src/main.py"):
            return httpx.Response(
                200,
                json={"type": "file", "content": file_content},
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    analyzer = RepositoryAnalyzer(
        GitHubClient(transport=httpx.MockTransport(handler)),
    )
    snapshot = asyncio.run(analyzer.analyze("https://github.com/owner/repository"))

    assert snapshot.metadata.default_branch == "main"
    assert snapshot.total_files_found == 3
    assert snapshot.files_analyzed == 2
    assert snapshot.files_skipped == 1
    assert snapshot.directories == ["src"]
    assert [file.path for file in snapshot.files] == ["README.md", "src/main.py"]
    assert snapshot.files[1].content == "print('hello')\n"


def test_repository_analyzer_respects_file_count_limit(monkeypatch) -> None:
    from app.analyzer import repository as repository_module

    monkeypatch.setattr(repository_module, "MAX_FILES", 1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/owner/repository":
            return httpx.Response(
                200,
                json={"name": "repository", "default_branch": "main"},
            )
        if request.url.path.endswith("/git/trees/main"):
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {"path": "README.md", "type": "blob", "size": 1},
                        {"path": "src/main.py", "type": "blob", "size": 1},
                    ]
                },
            )
        if request.url.path.endswith("/contents/README.md"):
            return httpx.Response(
                200,
                json={"type": "file", "content": base64.b64encode(b"x").decode()},
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    snapshot = asyncio.run(
        RepositoryAnalyzer(
            GitHubClient(transport=httpx.MockTransport(handler)),
        ).analyze("https://github.com/owner/repository")
    )

    assert snapshot.truncated is True
    assert snapshot.files_analyzed == 1
    assert snapshot.files_skipped == 1