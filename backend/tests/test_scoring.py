"""Tests for deterministic scoring engine."""

from app.models.report import (
    DependencyReport,
    Finding,
    RepositoryInfo,
    RepositorySnapshot,
    Severity,
)
from app.models.report import TestingReport as TestingReportModel
from app.scoring.engine import (
    CATEGORY_WEIGHTS,
    SCORED_CATEGORIES,
    calculate_scores,
)


def _meta() -> RepositoryInfo:
    return RepositoryInfo(
        url="https://github.com/owner/repo",
        owner="owner",
        name="repo",
        description="A sample project with solid documentation",
        default_branch="main",
        stars=10,
        forks=1,
        open_issues=0,
        language="Python",
        size_kb=12,
        topics=[],
    )


def _snapshot(**kwargs) -> RepositorySnapshot:
    base = dict(
        metadata=_meta(),
        findings=[],
        dependencies=DependencyReport(),
        testing=TestingReportModel(),
        files=[],
        directories=[],
    )
    base.update(kwargs)
    return RepositorySnapshot(**base)


def test_weights_sum_to_one() -> None:
    assert abs(sum(CATEGORY_WEIGHTS.values()) - 1.0) < 1e-9


def test_clean_repository_scores_high() -> None:
    from app.models.report import RepositoryFile

    snapshot = _snapshot(
        files=[
            RepositoryFile(path="README.md", size=100, content="# Hello"),
            RepositoryFile(path="LICENSE", size=50, content="MIT"),
            RepositoryFile(path="docs/guide.md", size=80, content="guide"),
        ],
        directories=["docs"],
        testing=TestingReportModel(
            tests_detected=True,
            test_file_count=3,
            frameworks=["pytest"],
            test_directories=["tests"],
        ),
        dependencies=DependencyReport(
            has_dependency_management=True,
            ecosystems=["Python"],
            manifests=["pyproject.toml"],
            lockfiles=["poetry.lock"],
            dependency_count=5,
            pinned_dependencies=5,
            loose_dependencies=0,
        ),
    )
    categories, overall = calculate_scores(snapshot)
    by_name = {c.category: c for c in categories}
    assert set(by_name) == set(SCORED_CATEGORIES)
    assert all(c.status.value == "complete" for c in categories)
    assert by_name["Code Quality"].score == 100.0
    assert by_name["Security"].score == 100.0
    assert by_name["Documentation"].score is not None
    assert by_name["Documentation"].score >= 70
    assert overall >= 80


def test_severity_deductions() -> None:
    findings = [
        Finding(
            title="secret",
            severity=Severity.CRITICAL,
            category="Security",
            description="bad",
        ),
        Finding(
            title="high",
            severity=Severity.HIGH,
            category="Security",
            description="bad",
        ),
        Finding(
            title="medium",
            severity=Severity.MEDIUM,
            category="Code Quality",
            description="bad",
        ),
        Finding(
            title="low",
            severity=Severity.LOW,
            category="Code Quality",
            description="bad",
        ),
        Finding(
            title="info",
            severity=Severity.INFO,
            category="Code Quality",
            description="note",
        ),
    ]
    categories, overall = calculate_scores(_snapshot(findings=findings))
    by_name = {c.category: c.score for c in categories}
    # Security: 100 - 25 - 15 = 60
    assert by_name["Security"] == 60.0
    # Quality: 100 - 8 - 3 = 89 (info = 0)
    assert by_name["Code Quality"] == 89.0
    assert 0 <= overall <= 100


def test_score_clamped_at_zero() -> None:
    findings = [
        Finding(
            title=f"c{i}",
            severity=Severity.CRITICAL,
            category="Security",
            description="x",
        )
        for i in range(10)
    ]
    categories, _ = calculate_scores(_snapshot(findings=findings))
    security = next(c for c in categories if c.category == "Security")
    assert security.score == 0.0


def test_architecture_not_in_scored_categories() -> None:
    assert "Architecture" not in SCORED_CATEGORIES
    assert "architecture" not in {k.lower() for k in CATEGORY_WEIGHTS}


def test_no_tests_reduces_testing_score() -> None:
    categories, _ = calculate_scores(
        _snapshot(testing=TestingReportModel(tests_detected=False))
    )
    testing = next(c for c in categories if c.category == "Testing")
    assert testing.score is not None
    assert testing.score <= 40.0


def test_overall_uses_weights() -> None:
    findings = [
        Finding(
            title="s",
            severity=Severity.CRITICAL,
            category="Security",
            description="x",
        )
    ]
    categories, overall = calculate_scores(
        _snapshot(
            findings=findings,
            testing=TestingReportModel(
                tests_detected=True, test_file_count=1, frameworks=["pytest"]
            ),
        )
    )
    by_name = {c.category: c.score for c in categories}
    expected = (
        by_name["Code Quality"] * 0.25
        + by_name["Security"] * 0.30
        + by_name["Testing"] * 0.20
        + by_name["Dependencies"] * 0.15
        + by_name["Documentation"] * 0.10
    )
    assert abs(overall - round(expected, 1)) < 0.15
