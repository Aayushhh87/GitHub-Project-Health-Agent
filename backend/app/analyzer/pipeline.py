from __future__ import annotations

import logging
from collections.abc import Callable

from app.analyzer.dependencies import analyze_dependencies
from app.analyzer.quality import analyze_quality
from app.analyzer.security import analyze_security
from app.analyzer.tests import analyze_tests
from app.models.report import (
    DependencyReport,
    Finding,
    RepositorySnapshot,
    TestingReport,
)

logger = logging.getLogger(__name__)

AnalyzerFunction = Callable[
    [RepositorySnapshot],
    tuple[object, list[Finding]] | list[Finding],
]


class AnalyzerPipeline:
    """
    Runs repository analyzers independently.

    A failure in one analyzer must not stop the remaining analyzers.
    """

    def __init__(
        self,
        analyzers: list[AnalyzerFunction] | None = None,
    ) -> None:
        self.analyzers = analyzers or [
            analyze_quality,
            analyze_security,
            analyze_dependencies,
            analyze_tests,
        ]

    def run(
        self,
        snapshot: RepositorySnapshot,
    ) -> list[Finding]:
        findings: list[Finding] = []

        for analyzer in self.analyzers:
            analyzer_name = getattr(
                analyzer,
                "__name__",
                analyzer.__class__.__name__,
            )

            try:
                result = analyzer(snapshot)

                if isinstance(result, tuple):
                    metadata, analyzer_findings = result

                    if analyzer is analyze_dependencies:
                        if isinstance(metadata, DependencyReport):
                            snapshot.dependencies = metadata

                    elif analyzer is analyze_tests:
                        if isinstance(metadata, TestingReport):
                            snapshot.testing = metadata

                    findings.extend(analyzer_findings)

                else:
                    findings.extend(result)

                logger.debug(
                    "Analyzer completed: %s findings=%d",
                    analyzer_name,
                    len(
                        result[1]
                        if isinstance(result, tuple)
                        else result
                    ),
                )

            except Exception:
                logger.exception(
                    "Analyzer failed: %s",
                    analyzer_name,
                )

                # One broken analyzer must never abort the entire scan.
                continue

        return findings