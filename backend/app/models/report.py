from enum import Enum
from typing import Literal

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
    description: str | None = None
    default_branch: str
    stars: int = Field(ge=0)
    forks: int = Field(ge=0)
    open_issues: int = Field(ge=0)
    language: str | None = None
    size_kb: int = Field(default=0, ge=0)
    topics: list[str] = Field(default_factory=list)


class RepositoryFile(BaseModel):
    path: str
    size: int = Field(default=0, ge=0)
    type: Literal["file"] = "file"
    language: str | None = None
    content: str | None = None
    skipped: bool = False
    skip_reason: str | None = None


class RepositoryFileSummary(BaseModel):
    path: str
    size: int = Field(default=0, ge=0)
    type: Literal["file"] = "file"
    language: str | None = None
    skipped: bool = False
    skip_reason: str | None = None


class Finding(BaseModel):
    title: str
    severity: Severity
    description: str
    evidence: list[str] = Field(default_factory=list)
    category: str = "General"
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    recommendation: str | None = None


class DependencyReport(BaseModel):
    has_dependency_management: bool = False
    ecosystems: list[str] = Field(default_factory=list)
    manifests: list[str] = Field(default_factory=list)
    lockfiles: list[str] = Field(default_factory=list)
    dependency_count: int | None = None
    production_dependencies: int | None = None
    development_dependencies: int | None = None
    pinned_dependencies: int | None = None
    loose_dependencies: int | None = None


class TestingReport(BaseModel):
    tests_detected: bool = False
    test_file_count: int = 0
    test_directories: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    evidence_files: list[str] = Field(default_factory=list)


class RepositorySnapshot(BaseModel):
    metadata: RepositoryInfo
    files: list[RepositoryFile] = Field(default_factory=list)
    directories: list[str] = Field(default_factory=list)
    total_files_found: int = Field(default=0, ge=0)
    files_analyzed: int = Field(default=0, ge=0)
    files_skipped: int = Field(default=0, ge=0)
    total_source_size: int = Field(default=0, ge=0)
    truncated: bool = False
    truncation_reason: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    dependencies: DependencyReport = Field(default_factory=DependencyReport)
    testing: TestingReport = Field(default_factory=TestingReport)


class RepositoryStatistics(BaseModel):
    total_files_found: int = Field(default=0, ge=0)
    files_analyzed: int = Field(default=0, ge=0)
    files_skipped: int = Field(default=0, ge=0)
    total_source_size: int = Field(default=0, ge=0)
    truncated: bool = False
    truncation_reason: str | None = None


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
    statistics: RepositoryStatistics = Field(default_factory=RepositoryStatistics)
    stats: RepositoryStatistics = Field(default_factory=RepositoryStatistics)
    dependencies: DependencyReport = Field(default_factory=DependencyReport)
    testing: TestingReport = Field(default_factory=TestingReport)
    languages: dict[str, int] = Field(default_factory=dict)
    files: list[RepositoryFileSummary] = Field(default_factory=list)
