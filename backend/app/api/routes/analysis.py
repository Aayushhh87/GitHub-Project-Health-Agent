from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.analyzer.repository import RepositoryAnalyzer, language_counts
from app.github.client import GitHubApiError
from app.github.url import GitHubUrlError, parse_github_url
from app.models.report import (
    AnalysisRequest,
    CategoryScore,
    CategoryStatus,
    HealthReport,
    RepositoryInfo,
    RepositoryFileSummary,
    RepositoryStatistics,
)

router = APIRouter()
analyzer = RepositoryAnalyzer()

PHASE_ONE_CATEGORIES = (
    "repository structure",
    "documentation",
    "engineering practices",
    "maintenance signals",
)


@router.post(
    "/analyze",
    response_model=HealthReport,
    status_code=status.HTTP_200_OK,
    summary="Analyze a public GitHub repository",
)
async def analyze_repository(
    payload: AnalysisRequest,
) -> HealthReport | JSONResponse:
    """Fetch and normalize repository evidence without running analyzers."""
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

    summary = (
        f"Collected {snapshot.files_analyzed} text files from "
        f"{snapshot.metadata.owner}/{snapshot.metadata.name} without cloning it."
    )
    if snapshot.files_skipped:
        summary += f" {snapshot.files_skipped} files were skipped safely."

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
        overall_score=None,
        category_scores=[
            CategoryScore(
                category=category,
                score=None,
                status=CategoryStatus.NOT_STARTED,
            )
            for category in PHASE_ONE_CATEGORIES
        ],
        summary=summary,
        findings=[],
        recommendations=[
            "Use the collected repository snapshot as input for the next analyzer phase.",
            "Keep evidence collection read-only; no repository code is executed.",
        ],
        phase="Phase 2 — repository ingestion",
        statistics=RepositoryStatistics(
            total_files_found=snapshot.total_files_found,
            files_analyzed=snapshot.files_analyzed,
            files_skipped=snapshot.files_skipped,
            total_source_size=snapshot.total_source_size,
            truncated=snapshot.truncated,
            truncation_reason=snapshot.truncation_reason,
        ),
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
    )
