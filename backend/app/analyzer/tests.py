import re
from pathlib import PurePosixPath

from app.models.report import Finding, RepositorySnapshot, Severity, TestingReport


TEST_DIRECTORY_NAMES = {"test", "tests", "__tests__", "spec"}
PYTHON_TEST_PATTERN = re.compile(r"(^test_[^/]+\.py$|^[^/]+_test\.py$)", re.I)
JS_TEST_PATTERN = re.compile(r"\.(?:test|spec)\.(?:js|jsx|ts|tsx)$", re.I)
GO_TEST_PATTERN = re.compile(r"_test\.go$", re.I)
JAVA_TEST_PATTERN = re.compile(r"Test\.java$", re.I)


def analyze_tests(
    snapshot: RepositorySnapshot,
) -> tuple[TestingReport, list[Finding]]:
    """Detect test evidence from paths and fetched configuration/source text only."""
    files = [
        file for file in snapshot.files
        if not file.skipped and file.content is not None
    ]
    test_files: list[str] = []
    test_directories: set[str] = set()
    evidence_files: set[str] = set()
    frameworks: set[str] = set()

    for file in files:
        path = file.path.replace("\\", "/")
        parts = PurePosixPath(path).parts
        directory_parts = parts[:-1]
        for index, part in enumerate(directory_parts):
            if part.lower() in TEST_DIRECTORY_NAMES:
                test_directories.add("/".join(parts[: index + 1]))
        name = parts[-1].lower()
        is_test_file = (
            PYTHON_TEST_PATTERN.match(name) is not None
            or JS_TEST_PATTERN.search(name) is not None
            or GO_TEST_PATTERN.search(name) is not None
            or JAVA_TEST_PATTERN.search(name) is not None
        )
        if is_test_file:
            test_files.append(path)
            evidence_files.add(path)

        content = file.content or ""
        lower = content.lower()
        basename = PurePosixPath(path).name.lower()
        if "pytest" in lower or basename in {"pytest.ini", "tox.ini"}:
            frameworks.add("pytest")
            evidence_files.add(path)
        if (
            "jest" in lower
            or "jest.config" in basename
            or "jest.config.js" in basename
            or "jest.config.ts" in basename
        ):
            frameworks.add("Jest")
            evidence_files.add(path)
        if "vitest" in lower or basename.startswith("vitest.config"):
            frameworks.add("Vitest")
            evidence_files.add(path)
        if "mocha" in lower or basename.startswith(".mocharc"):
            frameworks.add("Mocha")
            evidence_files.add(path)
        if "junit" in lower or "org.junit" in lower:
            frameworks.add("JUnit")
            evidence_files.add(path)
        if re.search(r"\b(?:import|from)\s+unittest\b", content):
            frameworks.add("unittest")
            evidence_files.add(path)
        if GO_TEST_PATTERN.search(name) or re.search(r"\bpackage\s+\w+\s*\n[\s\S]*\btesting\.T\b", content):
            frameworks.add("Go testing")
        if "#[cfg(test)]" in content or re.search(r"\bmod\s+tests\b", content):
            frameworks.add("Rust test")
            evidence_files.add(path)

    test_files.sort()
    directories = sorted(test_directories)
    evidence = sorted(evidence_files | set(test_files))
    tests_detected = bool(test_files or frameworks or test_directories)
    report = TestingReport(
        tests_detected=tests_detected,
        test_file_count=len(test_files),
        test_directories=directories,
        frameworks=sorted(frameworks),
        evidence_files=evidence,
    )
    if not tests_detected and files:
        finding = Finding(
            title="No automated tests detected",
            severity=Severity.MEDIUM,
            category="Testing",
            file=None,
            line=None,
            description="No common automated test files, directories, or framework configuration were found.",
            evidence=["Test detection checked common naming conventions and framework markers."],
            recommendation="Add automated tests appropriate to the project's runtime and critical behavior.",
        )
        return report, [finding]
    return report, []