import type { AnalysisRequest, HealthReport } from "../types/report";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export async function analyzeRepository(
  repositoryUrl: string,
): Promise<HealthReport> {
  const response = await fetch(`${apiBaseUrl}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repository_url: repositoryUrl,
    } satisfies AnalysisRequest),
  });

  const payload = (await response.json()) as
    | HealthReport
    | { detail?: string; error?: string };
  if (!response.ok) {
    throw new Error(
      "error" in payload && payload.error
        ? payload.error
        : "detail" in payload && payload.detail
          ? payload.detail
        : "The repository could not be analyzed.",
    );
  }

  return payload as HealthReport;
}
