from dataclasses import dataclass
from urllib.parse import urlparse

import re


class GitHubUrlError(ValueError):
    """Raised when a value is not a supported GitHub repository URL."""


@dataclass(frozen=True, slots=True)
class GitHubRepositoryRef:
    owner: str
    name: str
    normalized_url: str


_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def parse_github_url(value: str) -> GitHubRepositoryRef:
    """Parse a canonical HTTPS GitHub repository URL."""
    if not isinstance(value, str) or not value.strip():
        raise GitHubUrlError("Repository URL is required.")

    candidate = value.strip()
    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme.lower() != "https" or hostname not in {
        "github.com",
        "www.github.com",
    }:
        raise GitHubUrlError("URL must point to a GitHub repository.")

    if parsed.query or parsed.fragment:
        raise GitHubUrlError("Repository URL must not include a query or fragment.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise GitHubUrlError("URL must include a GitHub owner and repository name.")

    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]

    if not name or not _SEGMENT_PATTERN.fullmatch(owner) or not _SEGMENT_PATTERN.fullmatch(name):
        raise GitHubUrlError("GitHub owner and repository name are invalid.")

    return GitHubRepositoryRef(
        owner=owner,
        name=name,
        normalized_url=f"https://github.com/{owner}/{name}",
    )
