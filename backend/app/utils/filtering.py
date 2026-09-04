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

PRIORITY_FILE_NAMES = frozenset(
    {
        "readme",
        "readme.md",
        "readme.rst",
        "readme.txt",
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "pom.xml",
        "build.gradle",
        "dockerfile",
        "docker-compose.yml",
        ".env.example",
        ".gitignore",
    }
)

PRIORITY_DIRECTORIES = (
    ".github",
    "tests",
    "test",
    "src",
    "app",
    "backend",
    "frontend",
)


def is_ignored_path(path: str) -> bool:
    """Return whether any path segment belongs to an excluded directory."""
    return any(
        segment in IGNORED_DIRECTORIES
        for segment in PurePosixPath(path).parts
    )


def is_relevant_path(path: str) -> bool:
    """Apply only path and file-type filters, leaving size decisions to ingestion."""
    if is_ignored_path(path):
        return False

    name = PurePosixPath(path).name
    extension = PurePosixPath(name).suffix.lower()
    return name not in IGNORED_EXTENSIONS and extension not in IGNORED_EXTENSIONS


def should_include_file(path: str, size: int | None = None) -> bool:
    """Apply path, generated-file, binary-extension, and size filters."""
    if not is_relevant_path(path):
        return False

    return size is None or 0 <= size <= MAX_FILE_SIZE


def file_priority(path: str) -> int:
    """Return a deterministic priority for selecting files under collection limits."""
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name.lower()
    if name in PRIORITY_FILE_NAMES:
        return 0
    if any(
        normalized == directory or normalized.startswith(f"{directory}/")
        for directory in PRIORITY_DIRECTORIES
    ):
        return 2 if name.startswith("test") or "/test" in normalized else 3
    if "docs" in PurePosixPath(normalized).parts or "documentation" in PurePosixPath(normalized).parts:
        return 5
    return 6


def prioritize_paths(paths: list[str]) -> list[str]:
    """Sort paths consistently, preserving lexical order within each priority."""
    return sorted(paths, key=lambda path: (file_priority(path), path.lower(), path))


def within_source_limits(file_count: int, total_size: int) -> bool:
    """Check collection-wide safety limits."""
    return file_count <= MAX_FILES and total_size <= MAX_TOTAL_SOURCE_SIZE
