from dataclasses import dataclass
from typing import Any

from app.github.client import GitHubClient
from app.github.url import GitHubRepositoryRef


@dataclass(slots=True)
class GitHubRepository:
    """Repository-level facade used by future analyzers."""

    reference: GitHubRepositoryRef
    client: GitHubClient

    async def metadata(self) -> dict[str, Any]:
        return await self.client.get_repository(
            self.reference.owner,
            self.reference.name,
        )

    async def tree(self, reference: str = "HEAD") -> dict[str, Any]:
        return await self.client.get_tree(
            self.reference.owner,
            self.reference.name,
            reference,
        )

    async def file_contents(
        self,
        path: str,
        reference: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        return await self.client.get_file_contents(
            self.reference.owner,
            self.reference.name,
            path,
            reference,
        )
