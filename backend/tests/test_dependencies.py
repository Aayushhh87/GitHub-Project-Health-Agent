import json

from app.analyzer.dependencies import analyze_dependencies
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


def test_requirements_counts_pinned_and_loose_dependencies() -> None:
    report, findings = analyze_dependencies(
        snapshot_for(
            (
                "requirements.txt",
                "requests==2.31.0\nflask>=2.0\n# comment\nrich~=13.0\n",
            )
        )
    )

    assert report.has_dependency_management is True
    assert report.ecosystems == ["Python"]
    assert report.manifests == ["requirements.txt"]
    assert report.dependency_count == 3
    assert report.production_dependencies == 3
    assert report.pinned_dependencies == 1
    assert report.loose_dependencies == 2
    assert any(finding.title == "Broad dependency version specification" for finding in findings)


def test_pyproject_separates_project_and_development_dependencies() -> None:
    report, _ = analyze_dependencies(
        snapshot_for(
            (
                "pyproject.toml",
                "[project]\n"
                'dependencies = ["httpx==0.28.1"]\n'
                "[project.optional-dependencies]\n"
                'dev = ["pytest>=8.0"]\n',
            )
        )
    )

    assert report.dependency_count == 2
    assert report.production_dependencies == 1
    assert report.development_dependencies == 1


def test_package_json_and_lockfile_are_detected() -> None:
    package_json = json.dumps(
        {
            "dependencies": {"react": "18.3.1", "zod": "^3.0.0"},
            "devDependencies": {"vitest": "~2.0.0"},
        }
    )
    lockfile = json.dumps(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "demo"},
                "node_modules/react": {"version": "18.3.1"},
            },
        }
    )
    report, findings = analyze_dependencies(
        snapshot_for(("package.json", package_json), ("package-lock.json", lockfile))
    )

    assert report.ecosystems == ["JavaScript/TypeScript"]
    assert report.manifests == ["package.json"]
    assert report.lockfiles == ["package-lock.json"]
    assert report.dependency_count == 3
    assert not any(finding.title == "Dependency manifest has no lockfile" for finding in findings)


def test_java_go_rust_manifests_are_counted() -> None:
    report, _ = analyze_dependencies(
        snapshot_for(
            ("pom.xml", "<dependencies><dependency><version>1.2.3</version></dependency></dependencies>"),
            ("go.mod", "module example\n\nrequire (\n\tgithub.com/a/b v1.2.3\n\tgithub.com/c/d v1.0.0 // indirect\n)\n"),
            ("Cargo.toml", '[dependencies]\nserde = "1.0.0"\n[dev-dependencies]\nanyhow = "1.0"\n'),
        )
    )

    assert report.ecosystems == ["Go", "Java", "Rust"]
    assert report.dependency_count == 5
    assert report.development_dependencies == 1


def test_missing_manifest_is_informational() -> None:
    report, findings = analyze_dependencies(
        snapshot_for(("src/main.py", "print('hello')\n"))
    )

    assert report.has_dependency_management is False
    assert report.dependency_count is None
    finding = next(finding for finding in findings if finding.title == "No dependency manifest detected")
    assert finding.severity.value == "info"


def test_malformed_manifest_does_not_crash() -> None:
    report, findings = analyze_dependencies(
        snapshot_for(("package.json", '{"dependencies":'))
    )

    assert report.manifests == ["package.json"]
    assert any(finding.title == "Malformed dependency manifest" for finding in findings)