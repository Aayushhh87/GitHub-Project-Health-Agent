import ast
import re
from typing import Any

from app.models.report import Finding, RepositorySnapshot, Severity

MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 80
MAX_NESTING_DEPTH = 4
MAX_CYCLOMATIC_COMPLEXITY = 10

TODO_PATTERN = re.compile(r"\b(TODO|FIXME)\b(?:\s*[:\-]\s*)?(.*)", re.IGNORECASE)
DEBUG_PATTERN = re.compile(r"\b(?:console\.(?:log|debug|trace)|debugger)\b")
NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Match,
)


def analyze_quality(snapshot: RepositorySnapshot) -> list[Finding]:
    """Run safe, deterministic static checks over fetched text files."""
    findings: list[Finding] = []
    for file in snapshot.files:
        if file.skipped or file.content is None:
            continue
        try:
            findings.extend(_analyze_file(file.path, file.language, file.content))
        except Exception:
            # A malformed or unusual file must not prevent other files from being read.
            findings.append(
                Finding(
                    title="Quality checks could not parse this file",
                    severity=Severity.INFO,
                    category="Code Quality",
                    file=file.path,
                    description="The file was collected but could not be analyzed safely.",
                    evidence=["Static analysis skipped this file after an unexpected parser error."],
                    recommendation="Review the file with the language-specific tooling used by the project.",
                )
            )
    return findings


def _analyze_file(path: str, language: str | None, content: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = content.splitlines()
    if len(lines) > MAX_FILE_LINES:
        findings.append(
            _finding(
                title="Very long source file",
                severity=Severity.LOW,
                path=path,
                line=MAX_FILE_LINES + 1,
                description=f"This file contains {len(lines)} lines.",
                evidence=[f"Line count: {len(lines)} (threshold: {MAX_FILE_LINES})."],
                recommendation="Consider splitting the file into smaller cohesive modules.",
            )
        )

    for line_number, line in enumerate(lines, start=1):
        todo = TODO_PATTERN.search(line)
        if todo:
            marker = todo.group(1).upper()
            detail = todo.group(2).strip() or "follow-up work is marked in source"
            findings.append(
                _finding(
                    title=f"{marker} comment in source",
                    severity=Severity.LOW,
                    path=path,
                    line=line_number,
                    description="The file contains an explicit unfinished-work marker.",
                    evidence=[f"{marker}: {detail[:160]}"],
                    recommendation="Resolve the item or track it in the project's issue system.",
                )
            )

    if language in {"JavaScript", "TypeScript"}:
        findings.extend(_javascript_findings(path, lines))
    if language == "Python":
        findings.extend(_python_findings(path, content))
    return findings


def _python_findings(path: str, content: str) -> list[Finding]:
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as error:
        line = error.lineno or 1
        evidence = error.msg
        if error.text:
            evidence += f" — {error.text.strip()[:160]}"
        return [
            _finding(
                title="Python syntax error",
                severity=Severity.HIGH,
                path=path,
                line=line,
                description="Python AST parsing failed for this file.",
                evidence=[evidence],
                recommendation="Fix the syntax error before relying on automated tooling or importing this module.",
            )
        ]

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno)
            length = end_line - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                findings.append(
                    _finding(
                        title="Very long Python function",
                        severity=Severity.MEDIUM,
                        path=path,
                        line=node.lineno,
                        description=f"Function {node.name!r} spans {length} lines.",
                        evidence=[f"Function length: {length} lines (threshold: {MAX_FUNCTION_LINES})."],
                        recommendation="Split the function into smaller units with focused responsibilities.",
                    )
                )
            depth, depth_line = _max_nesting(node)
            if depth > MAX_NESTING_DEPTH:
                findings.append(
                    _finding(
                        title="Deeply nested Python logic",
                        severity=Severity.MEDIUM,
                        path=path,
                        line=depth_line,
                        description=f"Function {node.name!r} reaches nesting depth {depth}.",
                        evidence=[f"Nesting depth: {depth} (threshold: {MAX_NESTING_DEPTH})."],
                        recommendation="Use guard clauses or extract nested branches into named helpers.",
                    )
                )

        if isinstance(node, ast.ExceptHandler):
            is_broad = node.type is None or (
                isinstance(node.type, ast.Name)
                and node.type.id in {"Exception", "BaseException"}
            )
            if is_broad:
                findings.append(
                    _finding(
                        title="Broad exception handling",
                        severity=Severity.MEDIUM,
                        path=path,
                        line=node.lineno,
                        description="The code catches a broad exception type or every exception.",
                        evidence=["Broad except handler detected."],
                        recommendation="Catch the narrowest expected exception and handle unexpected failures separately.",
                    )
                )

    findings.extend(_unused_import_findings(path, tree))
    findings.extend(_radon_findings(path, content))
    return findings


def _max_nesting(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, int]:
    maximum = 0
    maximum_line = function.lineno

    def visit(node: ast.AST, depth: int) -> None:
        nonlocal maximum, maximum_line
        if isinstance(node, NESTING_NODES):
            depth += 1
            if depth > maximum:
                maximum = depth
                maximum_line = getattr(node, "lineno", maximum_line)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            visit(child, depth)

    visit(function, 0)
    return maximum, maximum_line


def _unused_import_findings(path: str, tree: ast.AST) -> list[Finding]:
    imported: list[tuple[str, int]] = []
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append((alias.asname or alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    imported.append((alias.asname or alias.name, node.lineno))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)

    return [
        _finding(
            title="Possibly unused import",
            severity=Severity.LOW,
            path=path,
            line=line,
            description=f"Imported name {name!r} is not referenced in this file.",
            evidence=[f"Import: {name}"],
            recommendation="Remove the import or use it explicitly; confirm side-effect imports before deleting.",
        )
        for name, line in imported
        if name not in used and not name.startswith("_")
    ]


def _radon_findings(path: str, content: str) -> list[Finding]:
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return []

    findings: list[Finding] = []
    try:
        blocks = cc_visit(content)
    except Exception:
        return []
    for block in blocks:
        complexity = getattr(block, "complexity", 0)
        if complexity > MAX_CYCLOMATIC_COMPLEXITY:
            findings.append(
                _finding(
                    title="High cyclomatic complexity",
                    severity=Severity.MEDIUM,
                    path=path,
                    line=getattr(block, "lineno", 1),
                    description=f"Block {getattr(block, 'name', 'unknown')!r} has high branching complexity.",
                    evidence=[
                        f"Cyclomatic complexity: {complexity} (threshold: {MAX_CYCLOMATIC_COMPLEXITY})."
                    ],
                    recommendation="Simplify branching or split the block into smaller functions.",
                )
            )
    return findings


def _javascript_findings(path: str, lines: list[str]) -> list[Finding]:
    return [
        _finding(
            title="Debug statement in source",
            severity=Severity.LOW,
            path=path,
            line=line_number,
            description="A console or debugger statement is present in JavaScript/TypeScript source.",
            evidence=[line.strip()[:160]],
            recommendation="Remove debug output or route intentional diagnostics through the project's logger.",
        )
        for line_number, line in enumerate(lines, start=1)
        if DEBUG_PATTERN.search(line)
    ]


def _finding(
    *,
    title: str,
    severity: Severity,
    path: str,
    line: int | None,
    description: str,
    evidence: list[str],
    recommendation: str,
) -> Finding:
    return Finding(
        title=title,
        severity=severity,
        category="Code Quality",
        file=path,
        line=line,
        description=description,
        evidence=evidence,
        recommendation=recommendation,
    )