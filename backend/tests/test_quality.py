from app.analyzer.quality import analyze_quality
from app.models.report import RepositoryFile, RepositoryInfo, RepositorySnapshot


def snapshot_for(path: str, content: str, language: str) -> RepositorySnapshot:
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
                language=language,
                content=content,
            )
        ],
        files_analyzed=1,
        total_files_found=1,
        total_source_size=len(content.encode()),
    )


def test_quality_detects_python_syntax_error() -> None:
    findings = analyze_quality(
        snapshot_for("broken.py", "def broken(:\n    return 1\n", "Python")
    )

    assert any(finding.title == "Python syntax error" for finding in findings)
    assert all(finding.category == "Code Quality" for finding in findings)


def test_quality_detects_todo_long_function_and_broad_exception() -> None:
    long_body = "\n".join("    value = 1" for _ in range(85))
    content = (
        "# TODO: remove this temporary branch\n"
        "def long_function():\n"
        f"{long_body}\n"
        "try:\n"
        "    work()\n"
        "except Exception:\n"
        "    pass\n"
    )

    findings = analyze_quality(snapshot_for("src/example.py", content, "Python"))
    titles = {finding.title for finding in findings}

    assert "TODO comment in source" in titles
    assert "Very long Python function" in titles
    assert "Broad exception handling" in titles
    assert all(finding.file == "src/example.py" for finding in findings)


def test_quality_detects_javascript_debug_statement() -> None:
    findings = analyze_quality(
        snapshot_for("src/app.ts", "console.log('debug');\nexport const ok = true;\n", "TypeScript")
    )

    assert any(finding.title == "Debug statement in source" for finding in findings)


def test_clean_code_does_not_produce_excessive_findings() -> None:
    findings = analyze_quality(
        snapshot_for(
            "src/clean.py",
            "def add(left: int, right: int) -> int:\n    return left + right\n",
            "Python",
        )
    )

    assert findings == []