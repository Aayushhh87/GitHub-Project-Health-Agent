import os
from typing import Any

import httpx


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
    ) -> None:
        self.timeout = timeout
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")

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
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

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
            f"/repos/{owner}/{name}/git/trees/{reference}",
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
            f"/repos/{owner}/{name}/contents/{path}",
            **params,
        )
