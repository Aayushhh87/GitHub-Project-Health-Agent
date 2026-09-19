from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any
from urllib.parse import quote

import httpx


logger = logging.getLogger(__name__)


class GitHubApiError(RuntimeError):
    """Safe application-level error raised for GitHub API failures."""

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        status_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.retry_after = retry_after
        self.user_message = message


class GitHubClient:
    """Async GitHub REST API client with safe retries and error handling."""

    base_url = "https://api.github.com"

    # Only transient failures are retried.
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 20.0,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.backoff_factor = max(0.0, backoff_factor)
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GitHub-Project-Health-Agent",
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
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.get(path, params=params)
                except httpx.TimeoutException as exc:
                    if attempt < self.max_retries:
                        await self._sleep_before_retry(attempt)
                        continue

                    raise GitHubApiError(
                        "GitHub took too long to respond. Please try again.",
                        kind="timeout",
                    ) from exc

                except httpx.RequestError as exc:
                    if attempt < self.max_retries:
                        await self._sleep_before_retry(attempt)
                        continue

                    raise GitHubApiError(
                        "GitHub could not be reached. Please try again.",
                        kind="network",
                    ) from exc

                if response.is_success:
                    return self._parse_json(response)

                error = self._build_api_error(response)

                if (
                    response.status_code in self.RETRYABLE_STATUS_CODES
                    and attempt < self.max_retries
                ):
                    delay = self._retry_delay(response, attempt)

                    logger.warning(
                        "GitHub API request failed: status=%s path=%s "
                        "attempt=%s/%s retry_in=%.2fs",
                        response.status_code,
                        path,
                        attempt + 1,
                        self.max_retries + 1,
                        delay,
                    )

                    await asyncio.sleep(delay)
                    continue

                raise error

        raise GitHubApiError(
            "GitHub request failed unexpectedly.",
            kind="api",
        )

    def _build_api_error(self, response: httpx.Response) -> GitHubApiError:
        status_code = response.status_code
        retry_after = self._retry_after(response)

        if status_code == 401:
            return GitHubApiError(
                "GitHub authentication failed. Check the configured token.",
                kind="authentication",
                status_code=status_code,
            )

        if status_code == 403:
            remaining = response.headers.get("x-ratelimit-remaining")

            if remaining == "0" or "rate limit" in response.text.lower():
                return GitHubApiError(
                    "GitHub's API rate limit was reached. Please try again later.",
                    kind="rate_limit",
                    status_code=status_code,
                    retry_after=retry_after,
                )

            return GitHubApiError(
                "GitHub denied access to this repository.",
                kind="forbidden",
                status_code=status_code,
            )

        if status_code == 404:
            return GitHubApiError(
                "Repository was not found or is private.",
                kind="not_found",
                status_code=status_code,
            )

        if status_code == 429:
            return GitHubApiError(
                "GitHub is rate limiting requests. Please try again later.",
                kind="rate_limit",
                status_code=status_code,
                retry_after=retry_after,
            )

        if status_code in {408, 500, 502, 503, 504}:
            return GitHubApiError(
                "GitHub is temporarily unavailable. Please try again.",
                kind="temporary",
                status_code=status_code,
                retry_after=retry_after,
            )

        return GitHubApiError(
            "GitHub returned an unexpected API error.",
            kind="api",
            status_code=status_code,
        )

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubApiError(
                "GitHub returned an unexpected response.",
                kind="invalid_response",
                status_code=response.status_code,
            ) from exc

    def _retry_delay(
        self,
        response: httpx.Response,
        attempt: int,
    ) -> float:
        retry_after = self._retry_after(response)

        if retry_after is not None:
            return min(float(retry_after), 30.0)

        return min(
            self.backoff_factor * (2**attempt),
            10.0,
        )

    @staticmethod
    def _retry_after(response: httpx.Response) -> int | None:
        value = response.headers.get("retry-after")

        if value:
            try:
                return max(0, int(value))
            except ValueError:
                pass

        reset = response.headers.get("x-ratelimit-reset")

        if reset:
            try:
                seconds = int(reset) - int(time.time())
                return max(0, seconds)
            except ValueError:
                pass

        return None

    async def _sleep_before_retry(self, attempt: int) -> None:
        delay = min(
            self.backoff_factor * (2**attempt),
            10.0,
        )

        logger.warning(
            "GitHub network error. Retrying in %.2fs.",
            delay,
        )

        await asyncio.sleep(delay)

    async def get_repository(
        self,
        owner: str,
        name: str,
    ) -> dict[str, Any]:
        """Fetch repository metadata."""
        return await self._get(f"/repos/{owner}/{name}")

    async def get_tree(
        self,
        owner: str,
        name: str,
        reference: str = "HEAD",
    ) -> dict[str, Any]:
        """Fetch a repository tree recursively."""
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