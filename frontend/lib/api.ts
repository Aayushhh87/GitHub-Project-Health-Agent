// import type { AnalysisRequest, HealthReport } from "../types/report";

// const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

// export async function analyzeRepository(
//   repositoryUrl: string,
// ): Promise<HealthReport> {
//   const response = await fetch(`${apiBaseUrl}/api/analyze`, {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({
//       repository_url: repositoryUrl,
//     } satisfies AnalysisRequest),
//   });

//   const payload = (await response.json()) as
//     | HealthReport
//     | { detail?: string; error?: string };
//   if (!response.ok) {
//     throw new Error(
//       "error" in payload && payload.error
//         ? payload.error
//         : "detail" in payload && payload.detail
//           ? payload.detail
//         : "The repository could not be analyzed.",
//     );
//   }

//   return payload as HealthReport;
// }


import type { AnalysisRequest, HealthReport } from "../types/report";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function analyzeRepository(
  repositoryUrl: string,
): Promise<HealthReport> {
  const response = await fetch(`${apiBaseUrl}/api/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      repository_url: repositoryUrl,
    } satisfies AnalysisRequest),
  });

  const contentType = response.headers.get("content-type") ?? "";
  const rawBody = await response.text();

  let payload:
    | HealthReport
    | { detail?: string; error?: string }
    | null = null;

  if (contentType.includes("application/json")) {
    try {
      payload = JSON.parse(rawBody);
    } catch {
      throw new Error(
        `Backend returned invalid JSON (HTTP ${response.status}).`,
      );
    }
  }

  if (!response.ok) {
    if (payload && "error" in payload && payload.error) {
      throw new Error(payload.error);
    }

    if (payload && "detail" in payload && payload.detail) {
      throw new Error(payload.detail);
    }

    throw new Error(
      rawBody ||
        `The repository could not be analyzed. HTTP ${response.status}`,
    );
  }

  if (!payload) {
    throw new Error("Backend returned an empty response.");
  }

  return payload as HealthReport;
}
