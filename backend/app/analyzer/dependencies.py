import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.models.report import DependencyReport, Finding, RepositorySnapshot, Severity


MANIFEST_ECOSYSTEMS = {
    "requirements.txt": "Python",
    "requirements-dev.txt": "Python",
    "pyproject.toml": "Python",
    "pipfile": "Python",
    "setup.py": "Python",
    "setup.cfg": "Python",
    "package.json": "JavaScript/TypeScript",
    "pom.xml": "Java",
    "build.gradle": "Java",
    "build.gradle.kts": "Java",
    "go.mod": "Go",
    "cargo.toml": "Rust",
    "composer.json": "PHP",
}

LOCKFILE_ECOSYSTEMS = {
    "package-lock.json": "JavaScript/TypeScript",
    "npm-shrinkwrap.json": "JavaScript/TypeScript",
    "yarn.lock": "JavaScript/TypeScript",
    "pnpm-lock.yaml": "JavaScript/TypeScript",
    "pipfile.lock": "Python",
    "poetry.lock": "Python",
    "go.sum": "Go",
    "cargo.lock": "Rust",
    "composer.lock": "PHP",
}

EXPECTED_LOCKFILES = {
    "JavaScript/TypeScript": {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml"},
    "Go": {"go.sum"},
    "Rust": {"cargo.lock"},
    "PHP": {"composer.lock"},
}


@dataclass
class _DependencyCounts:
    count: int = 0
    production: int = 0
    development: int = 0
    pinned: int = 0
    loose: int = 0

    def add(self, version: str | None, development: bool = False) -> None:
        self.count += 1
        if development:
            self.development += 1
        else:
            self.production += 1
        if _is_pinned(version):
            self.pinned += 1
        else:
            self.loose += 1


def analyze_dependencies(
    snapshot: RepositorySnapshot,
) -> tuple[DependencyReport, list[Finding]]:
    """Inspect fetched manifests without invoking package managers or installers."""
    manifest_files = [
        file for file in snapshot.files
        if not file.skipped
        and file.content is not None
        and PurePosixPath(file.path).name.lower() in MANIFEST_ECOSYSTEMS
    ]
    lockfile_files = [
        file for file in snapshot.files
        if not file.skipped
        and file.content is not None
        and PurePosixPath(file.path).name.lower() in LOCKFILE_ECOSYSTEMS
    ]
    ecosystems = sorted(
        {
            MANIFEST_ECOSYSTEMS[PurePosixPath(file.path).name.lower()]
            for file in manifest_files
        }
        | {
            LOCKFILE_ECOSYSTEMS[PurePosixPath(file.path).name.lower()]
            for file in lockfile_files
        }
    )
    manifests = sorted(file.path for file in manifest_files)
    lockfiles = sorted(file.path for file in lockfile_files)
    findings: list[Finding] = []
    counts = _DependencyCounts()
    parsed_any = False
    malformed: set[str] = set()

    for file in sorted(manifest_files, key=lambda item: item.path.lower()):
        try:
            parsed = _parse_manifest(
                PurePosixPath(file.path).name.lower(),
                file.content or "",
            )
            counts.count += parsed.count
            counts.production += parsed.production
            counts.development += parsed.development
            counts.pinned += parsed.pinned
            counts.loose += parsed.loose
            parsed_any = parsed_any or parsed.count > 0
            findings.extend(_risky_dependency_findings(file.path, file.content or ""))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            malformed.add(file.path)

    if not manifest_files and lockfile_files:
        for file in lockfile_files:
            try:
                parsed = _parse_lockfile(
                    PurePosixPath(file.path).name.lower(),
                    file.content or "",
                )
                counts.count += parsed.count
                counts.pinned += parsed.pinned
                counts.loose += parsed.loose
                parsed_any = parsed_any or parsed.count > 0
            except (ValueError, TypeError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError):
                malformed.add(file.path)

    for path in sorted(malformed):
        findings.append(
            _finding(
                title="Malformed dependency manifest",
                severity=Severity.MEDIUM,
                file=path,
                line=1,
                description="A dependency manifest was fetched but could not be parsed safely.",
                evidence=["Dependency metadata was skipped for this file."],
                recommendation="Fix the manifest syntax so dependency tooling can read it reliably.",
            )
        )

    if not manifest_files and not lockfile_files:
        findings.append(
            _finding(
                title="No dependency manifest detected",
                severity=Severity.INFO,
                file=None,
                line=None,
                description="No supported dependency manifest or lockfile was found in the analyzed files.",
                evidence=["Checked the supported dependency filenames in the fetched repository evidence."],
                recommendation="No action is needed if this repository intentionally has no external dependencies.",
            )
        )
    else:
        for ecosystem in ecosystems:
            if ecosystem not in EXPECTED_LOCKFILES:
                continue
            has_lockfile = any(
                PurePosixPath(path).name.lower() in EXPECTED_LOCKFILES[ecosystem]
                for path in lockfiles
            )
            if not has_lockfile:
                manifest = next(
                    (
                        file.path
                        for file in manifest_files
                        if MANIFEST_ECOSYSTEMS[PurePosixPath(file.path).name.lower()] == ecosystem
                    ),
                    None,
                )
                findings.append(
                    _finding(
                        title="Dependency manifest has no lockfile",
                        severity=Severity.LOW,
                        file=manifest,
                        line=1,
                        description=f"{ecosystem} dependency metadata is present without a recognized lockfile.",
                        evidence=[f"Expected one of: {', '.join(sorted(EXPECTED_LOCKFILES[ecosystem]))}."],
                        recommendation="Commit a lockfile when the ecosystem's workflow supports reproducible installs.",
                    )
                )

        if counts.loose:
            findings.append(
                _finding(
                    title="Broad dependency version specification",
                    severity=Severity.LOW,
                    file=manifests[0] if manifests else lockfiles[0],
                    line=_first_loose_line(manifest_files),
                    description=f"{counts.loose} dependency specification(s) are not pinned to an exact version.",
                    evidence=[f"Pinned: {counts.pinned}; loose or range-based: {counts.loose}."],
                    recommendation="Use deliberate version ranges or exact pins and review updates through a controlled workflow.",
                )
            )

    report = DependencyReport(
        has_dependency_management=bool(manifest_files or lockfile_files),
        ecosystems=ecosystems,
        manifests=manifests,
        lockfiles=lockfiles,
        dependency_count=counts.count if parsed_any else None,
        production_dependencies=counts.production if parsed_any else None,
        development_dependencies=counts.development if parsed_any else None,
        pinned_dependencies=counts.pinned if parsed_any else None,
        loose_dependencies=counts.loose if parsed_any else None,
    )
    return report, findings


def _parse_manifest(name: str, content: str) -> _DependencyCounts:
    counts = _DependencyCounts()
    if name in {"requirements.txt", "requirements-dev.txt"}:
        _parse_requirements(content, counts, development=name.endswith("-dev.txt"))
    elif name in {"pyproject.toml", "pipfile", "cargo.toml"}:
        _parse_toml(name, content, counts)
    elif name == "package.json":
        _parse_package_json(content, counts)
    elif name in {"setup.py", "setup.cfg"}:
        _parse_setup_file(name, content, counts)
    elif name == "pom.xml":
        _parse_pom(content, counts)
    elif name == "go.mod":
        _parse_go_mod(content, counts)
    elif name == "composer.json":
        _parse_composer(content, counts)
    return counts


def _parse_lockfile(name: str, content: str) -> _DependencyCounts:
    counts = _DependencyCounts()
    if name in {"package-lock.json", "npm-shrinkwrap.json", "composer.lock"}:
        data = json.loads(content)
        if name == "composer.lock":
            for section in ("packages", "packages-dev"):
                for package in data.get(section, []):
                    counts.add(package.get("version"), development=section.endswith("-dev"))
        else:
            packages = data.get("packages")
            if isinstance(packages, dict):
                for path, package in packages.items():
                    if path and path != "" and isinstance(package, dict) and "version" in package:
                        counts.add(str(package.get("version")))
            elif isinstance(data.get("dependencies"), dict):
                for package in data["dependencies"].values():
                    if isinstance(package, dict):
                        counts.add(package.get("version"))
    elif name == "cargo.lock":
        for match in re.finditer(r"(?ms)^\[\[package\]\]\s*(.*?)(?=^\[\[package\]\]|\Z)", content):
            version = re.search(r"^version\s*=\s*[\"']([^\"']+)", match.group(1), re.MULTILINE)
            counts.add(version.group(1) if version else None)
    elif name == "go.sum":
        for line in content.splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                counts.add(line.split()[1] if len(line.split()) > 1 else None)
    elif name in {"yarn.lock", "pnpm-lock.yaml", "pipfile.lock", "poetry.lock"}:
        for line in content.splitlines():
            if line and not line.startswith(("#", " ", "\t")) and (":" in line or "==" in line):
                counts.add(line.split(":", 1)[-1].strip())
    return counts


def _parse_requirements(content: str, counts: _DependencyCounts, development: bool) -> None:
    for line in content.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or stripped.startswith(("-", "--")):
            continue
        name = re.split(r"\s*(?:===|==|~=|!=|>=|<=|>|<)\s*", stripped, maxsplit=1)[0]
        if name and re.match(r"^[A-Za-z0-9_.-]+", name):
            counts.add(stripped[len(name):] or None, development=development)


def _parse_toml(name: str, content: str, counts: _DependencyCounts) -> None:
    data = tomllib.loads(content)
    if name == "pyproject.toml":
        project = data.get("project", {})
        for dependency in project.get("dependencies", []):
            _add_toml_dependency(counts, dependency)
        for values in project.get("optional-dependencies", {}).values():
            for dependency in values:
                _add_toml_dependency(counts, dependency, development=True)
        poetry = data.get("tool", {}).get("poetry", {})
        for dependency, spec in poetry.get("dependencies", {}).items():
            if dependency.lower() != "python":
                _add_toml_dependency(counts, spec)
        for values in poetry.get("dev-dependencies", {}).values():
            _add_toml_dependency(counts, values, development=True)
    elif name == "pipfile":
        for dependency, spec in data.get("packages", {}).items():
            _add_toml_dependency(counts, spec)
        for dependency, spec in data.get("dev-packages", {}).items():
            _add_toml_dependency(counts, spec, development=True)
    else:
        for section, development in (
            ("dependencies", False),
            ("dev-dependencies", True),
            ("build-dependencies", True),
        ):
            for spec in data.get(section, {}).values():
                _add_toml_dependency(counts, spec, development=development)


def _add_toml_dependency(counts: _DependencyCounts, spec: Any, development: bool = False) -> None:
    if isinstance(spec, dict):
        version = spec.get("version")
    elif isinstance(spec, str):
        version = spec
    else:
        version = None
    counts.add(version, development=development)


def _parse_package_json(content: str, counts: _DependencyCounts) -> None:
    data = json.loads(content)
    for section, development in (
        ("dependencies", False),
        ("optionalDependencies", False),
        ("peerDependencies", False),
        ("devDependencies", True),
    ):
        values = data.get(section, {})
        if isinstance(values, dict):
            for version in values.values():
                counts.add(str(version), development=development)


def _parse_setup_file(name: str, content: str, counts: _DependencyCounts) -> None:
    if name == "setup.py":
        for match in re.finditer(r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL):
            _parse_requirements(match.group(1).replace(",", "\n"), counts, development=False)
        for match in re.finditer(r"extras_require\s*=\s*\{(.*?)\}", content, re.DOTALL):
            _parse_requirements(match.group(1).replace(",", "\n"), counts, development=True)
    else:
        in_install = False
        for line in content.splitlines():
            if line.strip().startswith("["):
                in_install = line.strip().lower() == "[options]"
            elif in_install and line.strip().lower().startswith("install_requires"):
                continue
            elif in_install and line.startswith((" ", "\t")) and line.strip():
                _parse_requirements(line, counts, development=False)


def _parse_pom(content: str, counts: _DependencyCounts) -> None:
    for block in re.findall(r"(?is)<dependency>(.*?)</dependency>", content):
        version = re.search(r"(?is)<version>\s*([^<]+)", block)
        scope = re.search(r"(?is)<scope>\s*([^<]+)", block)
        counts.add(
            version.group(1).strip() if version else None,
            development=bool(scope and scope.group(1).strip().lower() in {"test", "provided"}),
        )


def _parse_go_mod(content: str, counts: _DependencyCounts) -> None:
    in_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
            continue
        if stripped.startswith("require ") and not stripped.endswith("("):
            parts = stripped.split()
            if len(parts) >= 3:
                counts.add(parts[2])
            continue
        if in_block and stripped and not stripped.startswith("//"):
            parts = stripped.split()
            if len(parts) >= 2:
                counts.add(parts[1])


def _parse_composer(content: str, counts: _DependencyCounts) -> None:
    data = json.loads(content)
    for section, development in (("require", False), ("require-dev", True)):
        values = data.get(section, {})
        if isinstance(values, dict):
            for version in values.values():
                counts.add(str(version), development=development)


def _is_pinned(version: str | None) -> bool:
    if not version:
        return False
    value = version.strip().strip("\"'")
    if value.startswith(("git+", "http:", "https:", "file:", "workspace:", "path:")):
        return False
    if value.startswith(("==", "===")):
        value = value.lstrip("=").strip()
    return bool(re.fullmatch(r"v?\d+(?:\.\d+){2}(?:[-+][0-9A-Za-z.-]+)?", value))


def _risky_dependency_findings(path: str, content: str) -> list[Finding]:
    findings: list[Finding] = []
    pattern = re.compile(r"(?:git\+http://|(?<![A-Za-z])http://|file:\.\.?/|[=:]\s*[\"']?\*[\"']?)", re.I)
    for number, line in enumerate(content.splitlines(), start=1):
        if pattern.search(line):
            findings.append(
                _finding(
                    title="Suspicious dependency source",
                    severity=Severity.MEDIUM,
                    file=path,
                    line=number,
                    description="A dependency specification uses an insecure or unusually broad source.",
                    evidence=[line.strip()[:240]],
                    recommendation="Review the source and prefer trusted registries, HTTPS, or reviewed local packages.",
                )
            )
    return findings


def _first_loose_line(files: list[Any]) -> int | None:
    for file in sorted(files, key=lambda item: item.path.lower()):
        for number, line in enumerate((file.content or "").splitlines(), start=1):
            if re.search(r"(^|[\"'=:\s])(?:\^|~|\*|>=|<=|>|<|workspace:|latest)(?=[0-9A-Za-z*~^<>=]|$)", line):
                return number
    return 1


def _finding(
    *,
    title: str,
    severity: Severity,
    file: str | None,
    line: int | None,
    description: str,
    evidence: list[str],
    recommendation: str,
) -> Finding:
    return Finding(
        title=title,
        severity=severity,
        category="Dependencies",
        file=file,
        line=line,
        description=description,
        evidence=evidence,
        recommendation=recommendation,
    )