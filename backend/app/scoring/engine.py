"""Deterministic, explainable scoring from repository evidence."""

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

SEVERITY_DEDUCTIONS: dict[Severity, float] = {
    Severity.CRITICAL: 25.0,
    Severity.HIGH: 15.0,
    Severity.MEDIUM: 8.0,
    Severity.LOW: 3.0,
    Severity.INFO: 0.0,
}

CATEGORY_WEIGHTS: dict[str, float] = {
    "Code Quality": 0.25,
    "Security": 0.30,
    "Testing": 0.20,
    "Dependencies": 0.15,
    "Documentation": 0.10,
}

SCORED_CATEGORIES = tuple(CATEGORY_WEIGHTS.keys())

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
    """Calculate category scores and the weighted overall score."""

    by_category = _group_findings(snapshot.findings)

    raw_scores = {
        "Code Quality": _score_from_findings(
            by_category["Code Quality"]
        ),
        "Security": _score_from_findings(
            by_category["Security"]
        ),
        "Testing": _score_testing(
            by_category["Testing"],
            snapshot.testing,
        ),
        "Dependencies": _score_dependencies(
            by_category["Dependencies"],
            snapshot.dependencies,
        ),
        "Documentation": _score_documentation(snapshot),
    }

    category_scores = [
        CategoryScore(
            category=category,
            score=round(raw_scores[category], 1),
            status=CategoryStatus.COMPLETE,
        )
        for category in SCORED_CATEGORIES
    ]

    overall = sum(
        raw_scores[category] * weight
        for category, weight in CATEGORY_WEIGHTS.items()
    )

    return category_scores, round(
        max(0.0, min(100.0, overall)),
        1,
    )


def _normalize_category(category: str) -> str | None:
    return _CATEGORY_ALIASES.get(category.strip().lower())


def _group_findings(
    findings: list[Finding],
) -> dict[str, list[Finding]]:
    grouped = {
        category: []
        for category in SCORED_CATEGORIES
    }

    for finding in findings:
        category = _normalize_category(finding.category)

        if category:
            grouped[category].append(finding)

    return grouped


def _finding_deduction(finding: Finding) -> float:
    """Calculate the score impact of one finding.

    Confidence reduces the impact of uncertain findings.
    score_impact, when provided, overrides the default severity impact.
    """

    base = finding.score_impact
    if finding.severity == Severity.INFO:
            return 0.0
        

    if base <= 0:
        base = SEVERITY_DEDUCTIONS.get(
            finding.severity,
            0.0,
        )

    return min(
        100.0,
        max(0.0, base * finding.confidence),
    )


def _score_from_findings(
    findings: list[Finding],
) -> float:
    """Score a category using evidence-backed findings."""

    total_deduction = sum(
        _finding_deduction(finding)
        for finding in findings
    )

    return max(
        0.0,
        min(100.0, 100.0 - total_deduction),
    )


def _score_testing(
    findings: list[Finding],
    testing: TestingReport,
) -> float:
    score = _score_from_findings(findings)

    if not testing.tests_detected:
        score = min(score, 40.0)

    elif (
        testing.test_file_count == 0
        and not testing.frameworks
    ):
        score = min(score, 55.0)

    return max(0.0, min(100.0, score))


def _score_dependencies(
    findings: list[Finding],
    dependencies: DependencyReport,
) -> float:
    score = _score_from_findings(findings)

    if not dependencies.has_dependency_management:
        return score

    loose = dependencies.loose_dependencies or 0
    total = dependencies.dependency_count or 0

    if total > 0:
        loose_ratio = loose / total

        if loose_ratio > 0.5:
            score = max(0.0, score - 5.0)

    return max(0.0, min(100.0, score))


def _score_documentation(
    snapshot: RepositorySnapshot,
) -> float:
    """Calculate documentation score from observable repository evidence."""

    paths = {
        file.path.replace("\\", "/").lower()
        for file in snapshot.files
        if not file.skipped
    }

    directories = {
        directory.replace("\\", "/").lower()
        for directory in snapshot.directories
    }

    score = 35.0

    readme_names = {
        "readme",
        "readme.md",
        "readme.rst",
        "readme.txt",
        "readme.markdown",
    }

    if any(
        PurePosixPath(path).name in readme_names
        for path in paths
    ):
        score += 30.0

    documentation_directories = {
        "docs",
        "doc",
        "documentation",
        "wiki",
    }

    if any(
        part in documentation_directories
        for path in paths | directories
        for part in PurePosixPath(path).parts
    ):
        score += 15.0

    if any(
        PurePosixPath(path).name
        in {
            "contributing.md",
            "contributing.rst",
            "contributing",
        }
        for path in paths
    ):
        score += 8.0

    if any(
        PurePosixPath(path).name
        in {
            "license",
            "license.md",
            "license.txt",
            "copying",
        }
        for path in paths
    ):
        score += 7.0

    if any(
        PurePosixPath(path).name
        in {
            "changelog.md",
            "changelog",
            "history.md",
            "changes.md",
        }
        for path in paths
    ):
        score += 5.0

    description = snapshot.metadata.description

    if description and len(description.strip()) > 20:
        score += 5.0

    return max(0.0, min(100.0, score))