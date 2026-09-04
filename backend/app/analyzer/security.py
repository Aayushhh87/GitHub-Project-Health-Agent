import re

from app.models.report import Finding, RepositorySnapshot, Severity

SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(api[_-]?key|access[_-]?key|secret|client[_-]?secret|token|password|passwd|private[_-]?key)
    \s*[:=]\s*
    (['"])([^'"\r\n]{8,})(\2)
    """
)
KNOWN_SECRET = re.compile(
    r"""(?x)
    \b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|
    AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{12,})\b
    """
)
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
PLACEHOLDER_VALUES = {
    "changeme",
    "change-me",
    "example",
    "placeholder",
    "password",
    "secret",
    "your-key-here",
    "your_token_here",
    "undefined",
    "null",
    "none",
}


def analyze_security(snapshot: RepositorySnapshot) -> list[Finding]:
    """Scan collected text for likely secrets and high-signal unsafe patterns."""
    findings: list[Finding] = []
    for file in snapshot.files:
        if file.skipped or file.content is None:
            continue
        try:
            findings.extend(_analyze_file(file.path, file.content))
        except Exception:
            continue
    return findings


def _analyze_file(path: str, content: str) -> list[Finding]:
    findings: list[Finding] = []
    reported_secret_lines: set[int] = set()

    for match in PRIVATE_KEY_PATTERN.finditer(content):
        line = _line_number(content, match.start())
        reported_secret_lines.add(line)
        findings.append(
            _finding(
                title="Private key material detected",
                severity=Severity.CRITICAL,
                path=path,
                line=line,
                description="A private-key header is present in repository text.",
                evidence=["Private key value masked; only the key type was retained."],
                recommendation="Remove the key from source history, rotate it, and load it from a secret manager.",
            )
        )

    for pattern in (KNOWN_SECRET, JWT_PATTERN):
        for match in pattern.finditer(content):
            line = _line_number(content, match.start())
            if line in reported_secret_lines:
                continue
            reported_secret_lines.add(line)
            findings.append(
                _finding(
                    title="Likely hardcoded credential",
                    severity=Severity.HIGH,
                    path=path,
                    line=line,
                    description="A token-shaped credential appears directly in repository text.",
                    evidence=[f"Possible credential detected: {_mask_secret(match.group(0))}"],
                    recommendation="Revoke and rotate the credential, then load it from environment or secret storage.",
                )
            )

    for match in SECRET_ASSIGNMENT.finditer(content):
        value = match.group(3).strip()
        line = _line_number(content, match.start())
        if line in reported_secret_lines or _is_placeholder(value):
            continue
        reported_secret_lines.add(line)
        key_name = match.group(1).lower()
        severity = Severity.CRITICAL if "private" in key_name else Severity.HIGH
        findings.append(
            _finding(
                title="Hardcoded secret-like value",
                severity=severity,
                path=path,
                line=line,
                description=f"A literal value is assigned to {match.group(1)}.",
                evidence=[f"{match.group(1)}={_mask_secret(value)}"],
                recommendation="Move the value to environment-based configuration and rotate it if it was real.",
            )
        )

    line_patterns: list[tuple[re.Pattern[str], str, Severity, str, str]] = [
        (
            re.compile(r"\b(?:eval|exec)\s*\("),
            "Dynamic code execution",
            Severity.HIGH,
            "The source invokes eval or exec.",
            "Avoid dynamic execution; use a constrained parser or explicit dispatch.",
        ),
        (
            re.compile(r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\([^)\n]*\bshell\s*=\s*True", re.I),
            "Shell execution through subprocess",
            Severity.HIGH,
            "A subprocess call enables shell interpretation.",
            "Pass an argument list without shell=True and validate all external input.",
        ),
        (
            re.compile(r"\bpickle\.(?:load|loads)\s*\("),
            "Unsafe pickle deserialization",
            Severity.HIGH,
            "Pickle deserialization can execute attacker-controlled object behavior.",
            "Use a data-only serialization format and validate untrusted input.",
        ),
        (
            re.compile(r"\bverify\s*=\s*False\b", re.I),
            "TLS certificate verification disabled",
            Severity.MEDIUM,
            "An HTTP client disables certificate verification.",
            "Keep TLS verification enabled and use a trusted certificate chain.",
        ),
        (
            re.compile(r"\ballow_origins\s*[:=]\s*[\[(][^]\n]*['\"]\*['\"]", re.I),
            "Overly permissive CORS",
            Severity.MEDIUM,
            "CORS configuration permits requests from every origin.",
            "Allow only the known frontend origins in production.",
        ),
        (
            re.compile(r"(?i)\b(?:select|insert|update|delete)\b[^\n]*(?:\+\s*|f['\"]|%s)"),
            "Potential SQL string construction",
            Severity.MEDIUM,
            "SQL-like text is combined with interpolation or string concatenation.",
            "Use parameterized queries through the database client.",
        ),
        (
            re.compile(r"(?i)\bdebug\s*[:=]\s*(?:true|1)\b"),
            "Debug mode enabled",
            Severity.MEDIUM,
            "A production-like configuration enables debug mode.",
            "Disable debug mode outside local development.",
        ),
        (
            re.compile(r"\bhttp://(?!localhost\b|127\.0\.0\.1\b)", re.I),
            "Insecure HTTP URL",
            Severity.LOW,
            "A non-local URL uses unencrypted HTTP.",
            "Use HTTPS for network communication unless an explicitly documented exception exists.",
        ),
    ]
    for line_number, line in enumerate(content.splitlines(), start=1):
        for pattern, title, severity, description, recommendation in line_patterns:
            match = pattern.search(line)
            if match:
                findings.append(
                    _finding(
                        title=title,
                        severity=severity,
                        path=path,
                        line=line_number,
                        description=description,
                        evidence=[_safe_line_evidence(line)],
                        recommendation=recommendation,
                    )
                )
    return findings


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        normalized in PLACEHOLDER_VALUES
        or normalized.startswith("your_")
        or normalized.startswith("<")
        or "getenv(" in normalized
        or "process.env" in normalized
    )


def _mask_secret(value: str) -> str:
    compact = value.strip()
    return f"{compact[:4]}********" if len(compact) > 4 else "********"


def _line_number(content: str, position: int) -> int:
    return content.count("\n", 0, position) + 1


def _safe_line_evidence(line: str) -> str:
    return line.strip()[:240]


def _finding(
    *,
    title: str,
    severity: Severity,
    path: str,
    line: int,
    description: str,
    evidence: list[str],
    recommendation: str,
) -> Finding:
    return Finding(
        title=title,
        severity=severity,
        category="Security",
        file=path,
        line=line,
        description=description,
        evidence=evidence,
        recommendation=recommendation,
    )