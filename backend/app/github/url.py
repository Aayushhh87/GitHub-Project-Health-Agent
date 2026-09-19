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


_SEGMENT_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
)


def parse_github_url(value: str) -> GitHubRepositoryRef:
    """Validate and normalize a GitHub repository URL."""

    if not isinstance(value, str):
        raise GitHubUrlError("Repository URL must be a string.")

    candidate = value.strip()

    if not candidate:
        raise GitHubUrlError("Repository URL is required.")

    if len(candidate) > 2048:
        raise GitHubUrlError("Repository URL is too long.")

    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme.lower() != "https":
        raise GitHubUrlError(
            "URL must be a valid GitHub repository URL using HTTPS."
        )

       
        
   

    if hostname not in {"github.com", "www.github.com"}:
        raise GitHubUrlError(
            "URL must point to a GitHub repository."
        )

    if parsed.username or parsed.password:
        raise GitHubUrlError(
            "Repository URL must not contain credentials."
        )

    if parsed.port is not None:
        raise GitHubUrlError(
            "Repository URL must not contain a custom port."
        )

    if parsed.query or parsed.fragment:
        raise GitHubUrlError(
            "Repository URL must not include a query or fragment."
        )

    parts = [
        part for part in parsed.path.split("/")
        if part
    ]

    if len(parts) != 2:
        raise GitHubUrlError(
            "URL must include a GitHub owner and repository name."
        )

    owner, name = parts

    if name.lower().endswith(".git"):
        name = name[:-4]

    if (
        not owner
        or not name
        or not _SEGMENT_PATTERN.fullmatch(owner)
        or not _SEGMENT_PATTERN.fullmatch(name)
    ):
        raise GitHubUrlError(
            "GitHub owner and repository name are invalid."
        )

    return GitHubRepositoryRef(
        owner=owner,
        name=name,
        normalized_url=(
            f"https://github.com/{owner}/{name}"
        ),
    )