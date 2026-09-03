from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CategoryStatus(str, Enum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    COMPLETE = "complete"


class AnalysisRequest(BaseModel):
    repository_url: str = Field(min_length=1)


class RepositoryInfo(BaseModel):
    url: str
    owner: str
    name: str


class Finding(BaseModel):
    title: str
    severity: Severity
    description: str
    evidence: list[str] = Field(default_factory=list)


class CategoryScore(BaseModel):
    category: str
    score: float | None = Field(default=None, ge=0, le=100)
    status: CategoryStatus


class HealthReport(BaseModel):
    repository: RepositoryInfo
    overall_score: float | None = Field(default=None, ge=0, le=100)
    category_scores: list[CategoryScore] = Field(default_factory=list)
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    phase: str
