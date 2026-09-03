import { Router, type IRouter } from "express";
import {
  AnalyzeRepositoryBody,
  AnalyzeRepositoryResponse,
} from "@workspace/api-zod";

const router: IRouter = Router();

const categories = [
  "repository structure",
  "documentation",
  "engineering practices",
  "maintenance signals",
] as const;

function parseRepositoryUrl(value: string) {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error("Repository URL must be a valid URL.");
  }

  if (
    parsed.protocol !== "https:" ||
    !["github.com", "www.github.com"].includes(parsed.hostname.toLowerCase()) ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error("URL must point to a GitHub repository.");
  }

  const parts = parsed.pathname.split("/").filter(Boolean);
  if (parts.length !== 2) {
    throw new Error("URL must include a GitHub owner and repository name.");
  }

  const [owner, rawName] = parts;
  const name = rawName.endsWith(".git") ? rawName.slice(0, -4) : rawName;
  if (!owner || !name || !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(owner) || !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(name)) {
    throw new Error("GitHub owner and repository name are invalid.");
  }

  return {
    owner,
    name,
    url: `https://github.com/${owner}/${name}`,
  };
}

router.post("/analyze", (req, res) => {
  try {
    const input = AnalyzeRepositoryBody.parse(req.body);
    const repository = parseRepositoryUrl(input.repository_url);
    const report = AnalyzeRepositoryResponse.parse({
      repository,
      overall_score: null,
      category_scores: categories.map((category) => ({
        category,
        score: null,
        status: "not_started",
      })),
      summary:
        "Repository accepted. Evidence collection and scoring will be implemented in a later phase.",
      findings: [],
      recommendations: [
        "Connect the GitHub REST client to collect repository evidence.",
        "Add category analyzers before enabling a health score.",
      ],
      phase: "Phase 1 — portable project foundation",
    });
    res.json(report);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request.";
    res.status(400).json({ error: message });
  }
});

export default router;
