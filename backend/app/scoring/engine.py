"""Deterministic category and overall scoring from repository evidence.

Architecture signals may be reported by the AI layer but never affect scores.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from app.models.report import (
    CategoryScore,
    CategoryStatus,
    DependencyReport,
    Finding,
    RepositorySnapshot,
    Severity,
    TestingReport,
)

SEVERITY_DEDUCTIONS: dict[Severity, int] = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 15,
    Severity.MEDIUM: 8,
    Severity.LOW: 3,
    Severity.INFO: 0,
}

# Weights must sum to 1.0. Architecture is intentionally excluded.
CATEGORY_WEIGHTS: dict[str, float] = {
    "Code Quality": 0.25,
    "Security": 0.30,
    "Testing": 0.20,
    "Dependencies": 0.15,
    "Documentation": 0.10,
}

SCORED_CATEGORIES = tuple(CATEGORY_WEIGHTS.keys())

# Map analyzer category labels onto scoring buckets.
_CATEGORY_ALIASES: dict[str, str] = {
    "code quality": "Code Quality",
    "quality": "Code Quality",
    "security": "Security",
    "dependencies": "Dependencies",
    "dependency": "Dependencies",
    "testing": "Testing",
    "tests": "Testing",
    "documentation": "Documentation",
    "docs": "Documentation",
}


def calculate_scores(
    snapshot: RepositorySnapshot,
) -> tuple[list[CategoryScore], float]:
    """Return completed category scores and a weighted overall score (0–100)."""
    by_category = _group_findings(snapshot.findings)

    quality = _score_from_findings(by_category.get("Code Quality", []))
    security = _score_from_findings(by_category.get("Security", []))
    testing = _score_testing(
        by_category.get("Testing", []),
        snapshot.testing,
    )
    dependencies = _score_dependencies(
        by_category.get("Dependencies", []),
        snapshot.dependencies,
    )
    documentation = _score_documentation(snapshot)

    raw = {
        "Code Quality": quality,
        "Security": security,
        "Testing": testing,
        "Dependencies": dependencies,
        "Documentation": documentation,
    }

    category_scores = [
        CategoryScore(
            category=name,
            score=round(raw[name], 1),
            status=CategoryStatus.COMPLETE,
        )
        for name in SCORED_CATEGORIES
    ]

    overall = 0.0
    for name, weight in CATEGORY_WEIGHTS.items():
        overall += raw[name] * weight
    overall = max(0.0, min(100.0, round(overall, 1)))
    return category_scores, overall


def _normalize_category(category: str) -> str | None:
    key = category.strip().lower()
    return _CATEGORY_ALIASES.get(key)


def _group_findings(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = {name: [] for name in SCORED_CATEGORIES}
    for finding in findings:
        bucket = _normalize_category(finding.category)
        if bucket:
            grouped[bucket].append(finding)
    return grouped


def _score_from_findings(findings: list[Finding]) -> float:
    score = 100.0
    for finding in findings:
        score -= SEVERITY_DEDUCTIONS.get(finding.severity, 0)
    return max(0.0, min(100.0, score))


def _score_testing(findings: list[Finding], testing: TestingReport) -> float:
    score = _score_from_findings(findings)
    if not testing.tests_detected:
        # Extra penalty when no tests exist and analyzers did not already flag it.
        if not any(f.severity in {Severity.MEDIUM, Severity.HIGH} for f in findings):
            score = min(score, 40.0)
    elif testing.test_file_count == 0 and not testing.frameworks:
        score = min(score, 55.0)
    return max(0.0, min(100.0, score))


def _score_dependencies(
    findings: list[Finding],
    dependencies: DependencyReport,
) -> float:
    score = _score_from_findings(findings)
    if not dependencies.has_dependency_management:
        # Language projects without manifests are not automatically failing;
        # keep neutral floor unless findings already deducted.
        return score
    if dependencies.loose_dependencies and dependencies.loose_dependencies > 0:
        # Mild extra pressure when many ranges are unconstrained.
        if dependencies.dependency_count and dependencies.dependency_count > 0:
            loose_ratio = dependencies.loose_dependencies / max(
                dependencies.dependency_count, 1
            )
            if loose_ratio > 0.5:
                score = min(score, score - 5)
    return max(0.0, min(100.0, score))


def _score_documentation(snapshot: RepositorySnapshot) -> float:
    """Heuristic documentation score from path evidence only."""
    paths = {
        file.path.replace("\\", "/").lower()
        for file in snapshot.files
        if not file.skipped
    }
    directories = {d.replace("\\", "/").lower() for d in snapshot.directories}

    score = 35.0  # baseline for any public repository

    readme_names = {
        "readme",
        "readme.md",
        "readme.rst",
        "readme.txt",
        "readme.markdown",
    }
    has_readme = any(PurePosixPath(p).name in readme_names for p in paths)
    if has_readme:
        score += 30.0

    doc_dirs = {"docs", "doc", "documentation", "wiki"}
    has_docs_dir = any(
        part in doc_dirs
        for path in paths | directories
        for part in PurePosixPath(path).parts
    )
    if has_docs_dir:
        score += 15.0

    contributing = any(
        PurePosixPath(p).name
        in {"contributing.md", "contributing.rst", "contributing"}
        for p in paths
    )
    if contributing:
        score += 8.0

    license_present = any(
        PurePosixPath(p).name in {"license", "license.md", "license.txt", "copying"}
        for p in paths
    )
    if license_present:
        score += 7.0

    changelog = any(
        PurePosixPath(p).name
        in {"changelog.md", "changelog", "history.md", "changes.md"}
        for p in paths
    )
    if changelog:
        score += 5.0

    # Description is a light documentation signal from repository metadata.
    if snapshot.metadata.description and len(snapshot.metadata.description.strip()) > 20:
        score += 5.0

    return max(0.0, min(100.0, score))
