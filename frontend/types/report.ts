export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type CategoryStatus = "not_started" | "pending" | "complete";

export interface AnalysisRequest {
  repository_url: string;
}

export interface RepositoryInfo {
  url: string;
  owner: string;
  name: string;
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
}
