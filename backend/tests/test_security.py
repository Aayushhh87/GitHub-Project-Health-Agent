from app.analyzer.security import analyze_security
from app.models.report import RepositoryFile, RepositoryInfo, RepositorySnapshot


def snapshot_for(content: str, path: str = "config.py") -> RepositorySnapshot:
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
                language="Python",
                content=content,
            )
        ],
        files_analyzed=1,
        total_files_found=1,
        total_source_size=len(content.encode()),
    )


def test_security_detects_and_masks_hardcoded_api_key_and_password() -> None:
    raw_key = "sk-1234567890abcdef"
    raw_password = "correct-horse-battery-staple"
    findings = analyze_security(
        snapshot_for(
            f'api_key = "{raw_key}"\npassword = "{raw_password}"\n'
        )
    )

    rendered = str(findings)
    assert any(finding.title == "Hardcoded secret-like value" for finding in findings)
    assert raw_key not in rendered
    assert raw_password not in rendered
    assert any("********" in evidence for finding in findings for evidence in finding.evidence)


def test_security_detects_private_key_and_unsafe_patterns() -> None:
    findings = analyze_security(
        snapshot_for(
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "eval(user_input)\n"
            "subprocess.run(command, shell=True)\n"
            "pickle.loads(payload)\n"
            "requests.get(url, verify=False)\n"
        )
    )
    titles = {finding.title for finding in findings}

    assert "Private key material detected" in titles
    assert "Dynamic code execution" in titles
    assert "Shell execution through subprocess" in titles
    assert "Unsafe pickle deserialization" in titles
    assert "TLS certificate verification disabled" in titles
    assert all(finding.category == "Security" for finding in findings)


def test_clean_code_has_no_security_findings() -> None:
    findings = analyze_security(
        snapshot_for(
            "import os\n\n"
            "def read_name() -> str:\n"
            "    return os.environ.get('NAME', 'anonymous')\n"
        )
    )

    assert findings == []