from fastapi.testclient import TestClient

from app.api.routes import analysis as analysis_route
from app.main import app
from app.models.report import RepositoryInfo, RepositorySnapshot

client = TestClient(app)


def fake_snapshot() -> RepositorySnapshot:
    return RepositorySnapshot(
        metadata=RepositoryInfo(
            url="https://github.com/owner/repository",
            owner="owner",
            name="repository",
            description="A test repository",
            default_branch="main",
            stars=12,
            forks=3,
            open_issues=1,
            language="Python",
            size_kb=42,
            topics=["testing"],
        ),
        total_files_found=2,
        files_analyzed=1,
        files_skipped=1,
        total_source_size=25,
    )


class StubAnalyzer:
    async def analyze(self, repository_url: str) -> RepositorySnapshot:
        return fake_snapshot()


def test_health_endpoint() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_valid_github_url(monkeypatch) -> None:
    monkeypatch.setattr(analysis_route, "analyzer", StubAnalyzer())
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/torvalds/linux"},
    )

    assert response.status_code == 200
    assert response.json()["repository"]["name"] == "repository"
    assert response.json()["statistics"]["files_analyzed"] == 1
    assert response.json()["phase"] == "Phase 2 — repository ingestion"


def test_invalid_github_url() -> None:
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://gitlab.com/owner/repository"},
    )

    assert response.status_code == 400


def test_github_url_with_trailing_slash(monkeypatch) -> None:
    monkeypatch.setattr(analysis_route, "analyzer", StubAnalyzer())
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/owner/repository/"},
    )

    assert response.status_code == 200
    assert response.json()["repository"]["url"] == "https://github.com/owner/repository"


def test_github_url_with_git_suffix(monkeypatch) -> None:
    monkeypatch.setattr(analysis_route, "analyzer", StubAnalyzer())
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/owner/repository.git"},
    )

    assert response.status_code == 200
    assert response.json()["repository"]["name"] == "repository"


def test_invalid_repository_input() -> None:
    response = client.post("/api/analyze", json={"repository_url": "not-a-url"})

    assert response.status_code == 400
    assert "GitHub" in response.json()["error"]