import os
from typing import Any
from urllib.parse import quote

import httpx


class GitHubApiError(RuntimeError):
    """A safe, application-level error raised for GitHub API failures."""

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.user_message = message


class GitHubClient:
    """Small async client for the GitHub REST API.

    It intentionally exposes only the evidence primitives needed by later
    analyzer phases and never shells out to clone or download a repository.
    """

    base_url = "https://api.github.com"

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get(self, path: str, **params: str) -> Any:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            try:
                response = await client.get(path, params=params)
            except httpx.TimeoutException as exc:
                raise GitHubApiError(
                    "GitHub took too long to respond. Please try again.",
                    kind="timeout",
                ) from exc
            except httpx.RequestError as exc:
                raise GitHubApiError(
                    "GitHub could not be reached. Please try again.",
                    kind="network",
                ) from exc

            if response.is_error:
                status_code = response.status_code
                if status_code == 401:
                    message = "GitHub authentication failed. Check the configured token."
                    kind = "authentication"
                elif status_code == 403 and (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or "rate limit" in response.text.lower()
                ):
                    message = "GitHub's API rate limit was reached. Please try again later."
                    kind = "rate_limit"
                elif status_code == 403:
                    message = "GitHub denied access to this repository."
                    kind = "forbidden"
                elif status_code == 404:
                    message = "Repository was not found or is private."
                    kind = "not_found"
                else:
                    message = "GitHub returned an unexpected API error."
                    kind = "api"
                raise GitHubApiError(
                    message,
                    kind=kind,
                    status_code=status_code,
                )

            try:
                return response.json()
            except ValueError as exc:
                raise GitHubApiError(
                    "GitHub returned an unexpected response.",
                    kind="invalid_response",
                    status_code=response.status_code,
                ) from exc

    async def get_repository(self, owner: str, name: str) -> dict[str, Any]:
        """Fetch repository metadata."""
        return await self._get(f"/repos/{owner}/{name}")

    async def get_tree(
        self,
        owner: str,
        name: str,
        reference: str = "HEAD",
    ) -> dict[str, Any]:
        """Fetch a repository tree recursively for a reference."""
        return await self._get(
            f"/repos/{owner}/{name}/git/trees/{quote(reference, safe='')}",
            recursive="1",
        )

    async def get_file_contents(
        self,
        owner: str,
        name: str,
        path: str,
        reference: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Fetch metadata and content for one repository path."""
        params = {"ref": reference} if reference else {}
        return await self._get(
            f"/repos/{owner}/{name}/contents/{quote(path, safe='/')}",
            **params,
        )
