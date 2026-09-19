
from __future__ import annotations

from app.models.report import Finding, RepositorySnapshot, Severity


def analyze_documentation(
    snapshot: RepositorySnapshot,
) -> list[Finding]:
    findings: list[Finding] = []

    file_paths = {
        repository_file.path.lower()
        for repository_file in snapshot.files
    }

    # README detection
    readme_files = {
        "readme.md",
        "readme",
        "readme.txt",
    }

    has_readme = bool(file_paths & readme_files)

    if not has_readme:
        findings.append(
            Finding(
                title="README documentation is missing",
                severity=Severity.MEDIUM,
                category="Documentation",
                description=(
                    "The repository does not contain a README file. "
                    "A README helps users understand the project's purpose, "
                    "setup process, usage, and structure."
                ),
                recommendation=(
                    "Add a README.md containing project overview, "
                    "installation steps, usage instructions, and "
                    "important configuration details."
                ),
                evidence=["No README file was found in the repository."],
                confidence=1.0,
                score_impact=8.0,
            )
        )

    # License detection
    license_files = {
        "license",
        "license.md",
        "license.txt",
        "copying",
    }

    has_license = bool(file_paths & license_files)

    if not has_license:
        findings.append(
            Finding(
                title="License file is missing",
                severity=Severity.LOW,
                category="Documentation",
                description=(
                    "The repository does not contain a recognizable "
                    "license file."
                ),
                recommendation=(
                    "Add an appropriate open-source license if the "
                    "project is intended for public use or distribution."
                ),
                evidence=["No recognized license file was found."],
                confidence=1.0,
                score_impact=3.0,
            )
        )

    return findings

