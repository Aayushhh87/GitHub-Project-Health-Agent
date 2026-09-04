import base64
import binascii
from collections import Counter
from typing import Any

from app.github.client import GitHubApiError, GitHubClient
from app.github.repository import GitHubRepository
from app.github.url import parse_github_url
from app.models.report import (
    RepositoryFile,
    RepositoryInfo,
    RepositorySnapshot,
)
from app.utils.filtering import (
    MAX_FILE_SIZE,
    MAX_FILES,
    MAX_TOTAL_SOURCE_SIZE,
    file_priority,
    is_relevant_path,
)
from app.utils.languages import detect_language


class RepositoryAnalyzer:
    """Fetch and safely normalize the evidence needed by later analyzers."""

    def __init__(self, client: GitHubClient | None = None) -> None:
        self.client = client or GitHubClient()

    async def analyze(self, repository_url: str) -> RepositorySnapshot:
        reference = parse_github_url(repository_url)
        repository = GitHubRepository(reference=reference, client=self.client)
        raw_metadata = await repository.metadata()
        metadata = self._metadata(raw_metadata, reference)
        raw_tree = await repository.tree(metadata.default_branch)

        entries = raw_tree.get("tree", [])
        file_entries = [
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("type") == "blob"
        ]
        directories = sorted(
            str(entry["path"])
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("type") == "tree"
            and isinstance(entry.get("path"), str)
        )
        relevant_entries = [
            entry
            for entry in file_entries
            if isinstance(entry.get("path"), str)
            and is_relevant_path(str(entry["path"]))
        ]
        relevant_entries.sort(
            key=lambda entry: (
                file_priority(str(entry["path"])),
                str(entry["path"]).lower(),
            )
        )

        files_skipped = len(file_entries) - len(relevant_entries)
        truncated = bool(raw_tree.get("truncated")) or len(relevant_entries) > MAX_FILES
        truncation_reason: str | None = None
        if raw_tree.get("truncated"):
            truncation_reason = "GitHub truncated the repository tree response."
        elif len(relevant_entries) > MAX_FILES:
            truncation_reason = (
                f"Only the first {MAX_FILES} relevant files were selected."
            )

        selected_entries = relevant_entries[:MAX_FILES]
        files_skipped += max(0, len(relevant_entries) - len(selected_entries))
        files: list[RepositoryFile] = []
        total_source_size = 0

        for entry in selected_entries:
            path = str(entry["path"])
            size = self._entry_size(entry)
            file = RepositoryFile(
                path=path,
                size=size,
                language=detect_language(path),
            )

            if size > MAX_FILE_SIZE:
                file.skipped = True
                file.skip_reason = (
                    f"File exceeds the {MAX_FILE_SIZE // 1024} KB file-size limit."
                )
                files_skipped += 1
                files.append(file)
                continue

            if total_source_size + size > MAX_TOTAL_SOURCE_SIZE:
                file.skipped = True
                file.skip_reason = "Total source-size limit reached."
                files_skipped += 1
                files.append(file)
                continue

            try:
                raw_contents = await repository.file_contents(
                    path,
                    metadata.default_branch,
                )
                content = decode_github_text(raw_contents, MAX_FILE_SIZE)
            except (GitHubApiError, ValueError, UnicodeError):
                content = None

            if content is None:
                file.skipped = True
                file.skip_reason = "File contents were unavailable or not valid text."
                files_skipped += 1
            else:
                file.content = content
                total_source_size += len(content.encode("utf-8"))
            files.append(file)

        return RepositorySnapshot(
            metadata=metadata,
            files=files,
            directories=directories,
            total_files_found=len(file_entries),
            files_analyzed=sum(1 for file in files if not file.skipped),
            files_skipped=files_skipped,
            total_source_size=total_source_size,
            truncated=truncated,
            truncation_reason=truncation_reason,
        )

    @staticmethod
    def _entry_size(entry: dict[str, Any]) -> int:
        size = entry.get("size", 0)
        return size if isinstance(size, int) and size >= 0 else 0

    @staticmethod
    def _metadata(raw: dict[str, Any], reference: Any) -> RepositoryInfo:
        owner = raw.get("owner")
        owner_name = owner.get("login") if isinstance(owner, dict) else None
        default_branch = raw.get("default_branch")
        return RepositoryInfo(
            url=reference.normalized_url,
            owner=str(owner_name or reference.owner),
            name=str(raw.get("name") or reference.name),
            description=raw.get("description")
            if isinstance(raw.get("description"), str)
            else None,
            default_branch=str(default_branch or "main"),
            stars=RepositoryAnalyzer._nonnegative_int(raw.get("stargazers_count")),
            forks=RepositoryAnalyzer._nonnegative_int(raw.get("forks_count")),
            open_issues=RepositoryAnalyzer._nonnegative_int(raw.get("open_issues_count")),
            language=raw.get("language")
            if isinstance(raw.get("language"), str)
            else None,
            size_kb=RepositoryAnalyzer._nonnegative_int(raw.get("size")),
            topics=[
                str(topic)
                for topic in raw.get("topics", [])
                if isinstance(topic, str)
            ],
        )

    @staticmethod
    def _nonnegative_int(value: Any) -> int:
        return value if isinstance(value, int) and value >= 0 else 0


def decode_github_text(
    payload: dict[str, Any] | list[dict[str, Any]],
    max_size: int = MAX_FILE_SIZE,
) -> str | None:
    """Decode one GitHub Contents API file response only when it is safe text."""
    if isinstance(payload, list) or payload.get("type") != "file":
        return None
    encoded = payload.get("content")
    if not isinstance(encoded, str):
        return None

    compact = "".join(encoded.split())
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error):
        return None
    if len(decoded) > max_size or b"\x00" in decoded:
        return None
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return None


def language_counts(snapshot: RepositorySnapshot) -> dict[str, int]:
    """Count detected languages for successfully analyzed files."""
    counts = Counter(
        file.language
        for file in snapshot.files
        if not file.skipped and file.language
    )
    return dict(sorted(counts.items()))