import asyncio

import httpx
import pytest

from app.github.client import GitHubApiError, GitHubClient


def test_not_found_is_converted_to_safe_application_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        max_retries=2,
    )

    with pytest.raises(GitHubApiError) as exc_info:
        asyncio.run(client.get_repository("missing", "repository"))

    error = exc_info.value

    assert error.kind == "not_found"
    assert error.status_code == 404
    assert error.user_message == "Repository was not found or is private."


def test_rate_limit_is_converted_to_safe_application_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "9999999999",
            },
            json={"message": "API rate limit exceeded"},
        )

    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )

    with pytest.raises(GitHubApiError) as exc_info:
        asyncio.run(client.get_repository("owner", "repository"))

    error = exc_info.value

    assert error.kind == "rate_limit"
    assert error.status_code == 403
    assert "rate limit" in error.user_message.lower()


def test_server_error_is_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            return httpx.Response(
                503,
                json={"message": "Service unavailable"},
            )

        return httpx.Response(
            200,
            json={"name": "repository"},
        )

    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        max_retries=2,
        backoff_factor=0,
    )

    result = asyncio.run(
        client.get_repository("owner", "repository")
    )

    assert result["name"] == "repository"
    assert attempts == 3


def test_network_error_is_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts < 2:
            raise httpx.ConnectError(
                "Connection failed",
                request=request,
            )

        return httpx.Response(
            200,
            json={"name": "repository"},
        )

    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        max_retries=1,
        backoff_factor=0,
    )

    result = asyncio.run(
        client.get_repository("owner", "repository")
    )

    assert result["name"] == "repository"
    assert attempts == 2


def test_authentication_error_is_not_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        return httpx.Response(
            401,
            json={"message": "Bad credentials"},
        )

    client = GitHubClient(
        transport=httpx.MockTransport(handler),
        max_retries=2,
        backoff_factor=0,
    )

    with pytest.raises(GitHubApiError) as exc_info:
        asyncio.run(client.get_repository("owner", "repository"))

    assert exc_info.value.kind == "authentication"
    assert attempts == 1


def test_successful_response_is_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Accept"] == "application/vnd.github+json"
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
        assert request.headers["User-Agent"] == "GitHub-Project-Health-Agent"

        return httpx.Response(
            200,
            json={"name": "repository", "private": False},
        )

    client = GitHubClient(
        token="test-token",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.get_repository("owner", "repository")
    )

    assert result["name"] == "repository"