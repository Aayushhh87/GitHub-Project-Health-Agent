from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_valid_github_url() -> None:
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/torvalds/linux"},
    )

    assert response.status_code == 200
    assert response.json()["repository"] == {
        "url": "https://github.com/torvalds/linux",
        "owner": "torvalds",
        "name": "linux",
    }


def test_invalid_github_url() -> None:
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://gitlab.com/owner/repository"},
    )

    assert response.status_code == 400


def test_github_url_with_trailing_slash() -> None:
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/owner/repository/"},
    )

    assert response.status_code == 200
    assert response.json()["repository"]["name"] == "repository"


def test_github_url_with_git_suffix() -> None:
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
