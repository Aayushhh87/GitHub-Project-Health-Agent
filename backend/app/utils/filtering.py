import os
from pathlib import PurePosixPath

MAX_FILES = int(os.getenv("MAX_FILES", "500"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(200 * 1024)))
MAX_TOTAL_SOURCE_SIZE = int(
    os.getenv("MAX_TOTAL_SOURCE_SIZE", str(10 * 1024 * 1024))
)

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "dist",
        "build",
        "coverage",
        "__pycache__",
        "target",
        "vendor",
    }
)

IGNORED_EXTENSIONS = frozenset(
    {
        ".7z",
        ".avi",
        ".bmp",
        ".class",
        ".dll",
        ".dmg",
        ".gif",
        ".ico",
        ".iso",
        ".jar",
        ".jpeg",
        ".jpg",
        ".mov",
        ".mp3",
        ".mp4",
        ".pdf",
        ".png",
        ".pyc",
        ".so",
        ".tar",
        ".tgz",
        ".tif",
        ".tiff",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".zip",
    }
)

GENERATED_FILE_NAMES = frozenset(
    {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "poetry.lock",
    }
)


def is_ignored_path(path: str) -> bool:
    """Return whether any path segment belongs to an excluded directory."""
    return any(
        segment in IGNORED_DIRECTORIES
        for segment in PurePosixPath(path).parts
    )


def should_include_file(path: str, size: int | None = None) -> bool:
    """Apply path, generated-file, binary-extension, and size filters."""
    if is_ignored_path(path):
        return False

    name = PurePosixPath(path).name
    extension = PurePosixPath(name).suffix.lower()
    if name in GENERATED_FILE_NAMES or extension in IGNORED_EXTENSIONS:
        return False

    return size is None or 0 <= size <= MAX_FILE_SIZE


def within_source_limits(file_count: int, total_size: int) -> bool:
    """Check collection-wide safety limits."""
    return file_count <= MAX_FILES and total_size <= MAX_TOTAL_SOURCE_SIZE
