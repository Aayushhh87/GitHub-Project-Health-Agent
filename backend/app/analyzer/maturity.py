
from __future__ import annotations

from app.models.report import Finding, RepositorySnapshot, Severity


def analyze_maturity(
    snapshot: RepositorySnapshot,
) -> list[Finding]:
    findings: list[Finding] = []

    file_paths = {
        repository_file.path.lower()
        for repository_file in snapshot.files
    }

    # CI/CD
    has_ci = any(
        path.startswith(".github/workflows/")
        and path.endswith((".yml", ".yaml"))
        for path in file_paths
    )

    if not has_ci:
        findings.append(
            Finding(
                title="CI/CD workflow is missing",
                severity=Severity.LOW,
                category="Project Maturity",
                description=(
                    "No GitHub Actions workflow was detected. "
                    "Automated testing, linting, or deployment may "
                    "not be configured."
                ),
                recommendation=(
                    "Consider adding a GitHub Actions workflow to "
                    "automatically run tests and quality checks."
                ),
                evidence=[
                    "No workflow file was found under .github/workflows/"
                ],
                confidence=1.0,
                score_impact=3.0,
            )
        )

    # Docker
    has_docker = any(
        path == "dockerfile"
        or path.endswith("/dockerfile")
        or path == "docker-compose.yml"
        or path == "docker-compose.yaml"
        for path in file_paths
    )

    if not has_docker:
        findings.append(
            Finding(
                title="Container configuration is missing",
                severity=Severity.INFO,
                category="Project Maturity",
                description=(
                    "No Docker configuration was detected."
                ),
                recommendation=(
                    "Consider adding Docker configuration if "
                    "containerized development or deployment is "
                    "useful for the project."
                ),
                evidence=[
                    "No Dockerfile or Docker Compose configuration was found."
                ],
                confidence=1.0,
                score_impact=0.0,
            )
        )

    return findings

