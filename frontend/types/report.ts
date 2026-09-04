export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type CategoryStatus = "not_started" | "pending" | "complete";

export interface AnalysisRequest {
  repository_url: string;
}

export interface RepositoryInfo {
  url: string;
  owner: string;
  name: string;
  description: string | null;
  default_branch: string;
  stars: number;
  forks: number;
  open_issues: number;
  language: string | null;
  size_kb: number;
  topics: string[];
}

export interface RepositoryStatistics {
  total_files_found: number;
  files_analyzed: number;
  files_skipped: number;
  total_source_size: number;
  truncated: boolean;
  truncation_reason: string | null;
}

export interface RepositoryFileSummary {
  path: string;
  size: number;
  type: "file";
  language: string | null;
  skipped: boolean;
  skip_reason: string | null;
}

export interface Finding {
  title: string;
  severity: Severity;
  description: string;
  evidence: string[];
}

export interface CategoryScore {
  category: string;
  score: number | null;
  status: CategoryStatus;
}

export interface HealthReport {
  repository: RepositoryInfo;
  overall_score: number | null;
  category_scores: CategoryScore[];
  summary: string;
  findings: Finding[];
  recommendations: string[];
  phase: string;
  statistics: RepositoryStatistics;
  languages: Record<string, number>;
  files: RepositoryFileSummary[];
}
