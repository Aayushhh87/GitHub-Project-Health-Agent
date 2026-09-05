from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.ai.analyzer import analyze_with_ai
from app.analyzer.repository import RepositoryAnalyzer, language_counts
from app.github.client import GitHubApiError
from app.github.url import GitHubUrlError, parse_github_url
from app.models.report import (
    AnalysisRequest,
    HealthReport,
    RepositoryFileSummary,
    RepositoryInfo,
    RepositoryStatistics,
)
from app.scoring.engine import calculate_scores

router = APIRouter()
analyzer = RepositoryAnalyzer()


@router.post(
    "/analyze",
    response_model=HealthReport,
    status_code=status.HTTP_200_OK,
    summary="Analyze a public GitHub repository",
)
async def analyze_repository(
    payload: AnalysisRequest,
) -> HealthReport | JSONResponse:
    """Fetch repository evidence, run deterministic analyzers, score, and optionally synthesize with AI."""
    try:
        repository = parse_github_url(payload.repository_url)
        snapshot = await analyzer.analyze(payload.repository_url)
    except GitHubUrlError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(exc)},
        )
    except GitHubApiError as exc:
        response_status = {
            "authentication": status.HTTP_502_BAD_GATEWAY,
            "forbidden": status.HTTP_403_FORBIDDEN,
            "not_found": status.HTTP_404_NOT_FOUND,
            "rate_limit": status.HTTP_429_TOO_MANY_REQUESTS,
            "timeout": status.HTTP_504_GATEWAY_TIMEOUT,
            "network": status.HTTP_502_BAD_GATEWAY,
        }.get(exc.kind, status.HTTP_502_BAD_GATEWAY)
        return JSONResponse(
            status_code=response_status,
            content={"error": exc.user_message},
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": "Repository ingestion failed unexpectedly."},
        )

    category_scores, overall_score = calculate_scores(snapshot)

    summary = (
        f"Collected {snapshot.files_analyzed} text files from "
        f"{snapshot.metadata.owner}/{snapshot.metadata.name} without cloning it. "
        f"Found {len(snapshot.findings)} deterministic quality, security, dependency, "
        f"and testing signals. Overall health score: {overall_score}."
    )
    if snapshot.files_skipped:
        summary += f" {snapshot.files_skipped} files were skipped safely."

    recommendations = [
        "Review findings alongside their file, line, and manifest evidence.",
        "Use committed lockfiles and deliberate version ranges where the ecosystem supports them.",
        "Keep analysis read-only; dependencies are never installed and repository code is never executed.",
    ]

    strengths: list[str] = []
    weaknesses: list[str] = []
    architecture_insight: str | None = None
    documentation_insight: str | None = None
    ai_enabled = False

    ai_result = await analyze_with_ai(
        snapshot,
        overall_score=overall_score,
        category_scores=[
            {"category": c.category, "score": c.score, "status": c.status.value}
            for c in category_scores
        ],
    )
    if ai_result is not None:
        ai_enabled = True
        if ai_result.summary:
            summary = ai_result.summary
        if ai_result.recommendations:
            recommendations = ai_result.recommendations
        strengths = ai_result.strengths
        weaknesses = ai_result.weaknesses
        architecture_insight = ai_result.architecture_insight or None
        documentation_insight = ai_result.documentation_insight or None

    statistics = RepositoryStatistics(
        total_files_found=snapshot.total_files_found,
        files_analyzed=snapshot.files_analyzed,
        files_skipped=snapshot.files_skipped,
        total_source_size=snapshot.total_source_size,
        truncated=snapshot.truncated,
        truncation_reason=snapshot.truncation_reason,
    )

    return HealthReport(
        repository=RepositoryInfo(
            url=repository.normalized_url,
            owner=repository.owner,
            name=snapshot.metadata.name,
            description=snapshot.metadata.description,
            default_branch=snapshot.metadata.default_branch,
            stars=snapshot.metadata.stars,
            forks=snapshot.metadata.forks,
            open_issues=snapshot.metadata.open_issues,
            language=snapshot.metadata.language,
            size_kb=snapshot.metadata.size_kb,
            topics=snapshot.metadata.topics,
        ),
        overall_score=overall_score,
        category_scores=category_scores,
        summary=summary,
        findings=snapshot.findings,
        recommendations=recommendations,
        phase="Phase 5 — AI analysis and deterministic scoring",
        statistics=statistics,
        stats=statistics,
        dependencies=snapshot.dependencies,
        testing=snapshot.testing,
        languages=language_counts(snapshot),
        files=[
            RepositoryFileSummary(
                path=file.path,
                size=file.size,
                language=file.language,
                skipped=file.skipped,
                skip_reason=file.skip_reason,
            )
            for file in snapshot.files
        ],
        strengths=strengths,
        weaknesses=weaknesses,
        architecture_insight=architecture_insight,
        documentation_insight=documentation_insight,
        ai_enabled=ai_enabled,
    )
