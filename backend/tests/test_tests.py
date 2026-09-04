from app.analyzer.tests import analyze_tests
from app.models.report import RepositoryFile, RepositoryInfo, RepositorySnapshot


def snapshot_for(*files: tuple[str, str]) -> RepositorySnapshot:
    return RepositorySnapshot(
        metadata=RepositoryInfo(
            url="https://github.com/owner/repository",
            owner="owner",
            name="repository",
            default_branch="main",
            stars=0,
            forks=0,
            open_issues=0,
        ),
        files=[
            RepositoryFile(
                path=path,
                size=len(content.encode()),
                content=content,
            )
            for path, content in files
        ],
        files_analyzed=len(files),
        total_files_found=len(files),
        total_source_size=sum(len(content.encode()) for _, content in files),
    )


def test_detects_tests_directory_and_pytest_files() -> None:
    report, findings = analyze_tests(
        snapshot_for(
            ("tests/test_api.py", "import pytest\n\ndef test_health():\n    assert True\n"),
            ("pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"),
        )
    )

    assert report.tests_detected is True
    assert report.test_file_count == 1
    assert report.test_directories == ["tests"]
    assert report.frameworks == ["pytest"]
    assert "tests/test_api.py" in report.evidence_files
    assert findings == []


def test_detects_jest_vitest_junit_and_go_conventions() -> None:
    report, _ = analyze_tests(
        snapshot_for(
            ("src/button.test.ts", "describe('button', () => {});\n"),
            ("src/button.spec.ts", "import { describe } from 'vitest';\n"),
            ("WidgetTest.java", "import org.junit.Test;\n"),
            ("pkg/handler_test.go", "package pkg\n\nimport \"testing\"\n"),
            ("vitest.config.ts", "export default { test: {} };\n"),
        )
    )

    assert report.tests_detected is True
    assert report.test_file_count == 4
    assert set(report.frameworks) == {"Go testing", "JUnit", "Vitest"}


def test_repository_with_no_tests_gets_conservative_finding() -> None:
    report, findings = analyze_tests(
        snapshot_for(("src/main.py", "def main():\n    return 1\n"))
    )

    assert report.tests_detected is False
    assert report.test_file_count == 0
    assert len(findings) == 1
    assert findings[0].title == "No automated tests detected"
    assert findings[0].severity.value == "medium"


def test_malformed_or_unusual_test_source_does_not_crash() -> None:
    report, _ = analyze_tests(
        snapshot_for(("tests/strange.py", "\x00not source\x00"))
    )

    assert report.tests_detected is True