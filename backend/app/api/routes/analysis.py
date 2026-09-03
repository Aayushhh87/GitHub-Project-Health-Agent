from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.github.url import GitHubUrlError, parse_github_url
from app.models.report import (
    AnalysisRequest,
    CategoryScore,
    CategoryStatus,
    HealthReport,
    RepositoryInfo,
)

router = APIRouter()

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
def analyze_repository(payload: AnalysisRequest) -> HealthReport:
    """Validate a repository URL and return the Phase 1 report shape."""
    try:
        repository = parse_github_url(payload.repository_url)
    except GitHubUrlError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(exc)},
        )

    return HealthReport(
        repository=RepositoryInfo(
            url=repository.normalized_url,
            owner=repository.owner,
            name=repository.name,
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
        summary=(
            "Repository accepted. Evidence collection and scoring will be "
            "implemented in a later phase."
        ),
        findings=[],
        recommendations=[
            "Connect the GitHub REST client to collect repository evidence.",
            "Add category analyzers before enabling a health score.",
        ],
        phase="Phase 1 — portable project foundation",
    )
