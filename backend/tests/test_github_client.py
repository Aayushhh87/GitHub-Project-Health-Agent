import asyncio

import httpx

from app.github.client import GitHubApiError, GitHubClient


def test_not_found_is_converted_to_safe_application_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    client = GitHubClient(transport=httpx.MockTransport(handler))

    try:
        asyncio.run(client.get_repository("missing", "repository"))
    except GitHubApiError as error:
        assert error.kind == "not_found"
        assert error.user_message == "Repository was not found or is private."
    else:
        raise AssertionError("Expected GitHubApiError")


def test_rate_limit_is_converted_to_safe_application_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0"},
            json={"message": "API rate limit exceeded"},
        )

    client = GitHubClient(transport=httpx.MockTransport(handler))

    try:
        asyncio.run(client.get_repository("owner", "repository"))
    except GitHubApiError as error:
        assert error.kind == "rate_limit"
        assert "rate limit" in error.user_message
    else:
        raise AssertionError("Expected GitHubApiError")