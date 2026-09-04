import { Router, type IRouter } from "express";
import {
  AnalyzeRepositoryBody,
  AnalyzeRepositoryResponse,
} from "@workspace/api-zod";

const router: IRouter = Router();

const MAX_FILES = 500;
const MAX_FILE_SIZE = 200 * 1024;
const MAX_TOTAL_SOURCE_SIZE = 10 * 1024 * 1024;
const ignoredDirectories = new Set([
  ".git",
  "node_modules",
  "venv",
  ".venv",
  "dist",
  "build",
  "coverage",
  "__pycache__",
  "target",
  "vendor",
  ".cache",
]);
const ignoredExtensions = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".svg",
  ".mp4",
  ".mov",
  ".avi",
  ".zip",
  ".tar",
  ".gz",
  ".rar",
  ".7z",
  ".pdf",
  ".exe",
  ".dll",
  ".so",
  ".class",
  ".pyc",
]);
const languageByExtension: Record<string, string> = {
  ".py": "Python",
  ".js": "JavaScript",
  ".jsx": "JavaScript",
  ".ts": "TypeScript",
  ".tsx": "TypeScript",
  ".java": "Java",
  ".c": "C",
  ".h": "C",
  ".cc": "C++",
  ".cpp": "C++",
  ".cxx": "C++",
  ".hpp": "C++",
  ".cs": "C#",
  ".go": "Go",
  ".rs": "Rust",
  ".php": "PHP",
  ".rb": "Ruby",
  ".kt": "Kotlin",
  ".kts": "Kotlin",
  ".swift": "Swift",
  ".html": "HTML",
  ".css": "CSS",
  ".scss": "SCSS",
  ".json": "JSON",
  ".yaml": "YAML",
  ".yml": "YAML",
  ".md": "Markdown",
  ".mdx": "Markdown",
  ".sh": "Shell",
};

type GitHubTreeEntry = {
  path: string;
  type: "blob" | "tree";
  size?: number;
};

class GitHubRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

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
  if (
    !owner ||
    !name ||
    !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(owner) ||
    !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(name)
  ) {
    throw new Error("GitHub owner and repository name are invalid.");
  }

  return {
    owner,
    name,
    url: `https://github.com/${owner}/${name}`,
  };
}

function isRelevantPath(path: string) {
  const parts = path.split("/");
  const fileName = parts.at(-1) ?? "";
  const extension = fileName.includes(".")
    ? `.${fileName.split(".").at(-1)?.toLowerCase()}`
    : "";
  return (
    !parts.some((part) => ignoredDirectories.has(part)) &&
    !ignoredExtensions.has(extension)
  );
}

function filePriority(path: string) {
  const normalized = path.toLowerCase();
  const fileName = normalized.split("/").at(-1) ?? "";
  if (
    [
      "readme.md",
      "readme.rst",
      "readme.txt",
      "requirements.txt",
      "pyproject.toml",
      "package.json",
      "package-lock.json",
      "pnpm-lock.yaml",
      "yarn.lock",
      "dockerfile",
      ".env.example",
      ".gitignore",
    ].includes(fileName)
  ) {
    return 0;
  }
  if (normalized.startsWith(".github/")) return 2;
  if (normalized.startsWith("tests/") || normalized.startsWith("test/")) {
    return 4;
  }
  if (normalized.startsWith("src/") || normalized.startsWith("app/")) return 3;
  if (normalized.startsWith("docs/")) return 5;
  return 6;
}

function detectLanguage(path: string) {
  const dot = path.lastIndexOf(".");
  return dot >= 0 ? languageByExtension[path.slice(dot).toLowerCase()] ?? null : null;
}

async function githubGet<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`https://api.github.com${path}`, {
      headers: {
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        ...(process.env.GITHUB_TOKEN
          ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` }
          : {}),
      },
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    throw new GitHubRequestError(
      "GitHub could not be reached or timed out. Please try again.",
      504,
    );
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new GitHubRequestError(
        "GitHub authentication failed. Check the configured token.",
        502,
      );
    }
    if (response.status === 403) {
      throw new GitHubRequestError(
        "GitHub denied access or its API rate limit was reached.",
        429,
      );
    }
    if (response.status === 404) {
      throw new GitHubRequestError(
        "Repository was not found or is private.",
        404,
      );
    }
    throw new GitHubRequestError("GitHub returned an unexpected API error.", 502);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new GitHubRequestError("GitHub returned an unexpected response.", 502);
  }
}

async function fetchFileText(
  owner: string,
  name: string,
  path: string,
  branch: string,
) {
  const payload = await githubGet<{
    type?: string;
    content?: string;
  }>(
    `/repos/${owner}/${name}/contents/${path
      .split("/")
      .map(encodeURIComponent)
      .join("/")}?ref=${encodeURIComponent(branch)}`,
  );
  if (payload.type !== "file" || !payload.content) return null;
  const compact = payload.content.replace(/\s/g, "");
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(compact)) return null;
  const bytes = Buffer.from(compact, "base64");
  if (bytes.length > MAX_FILE_SIZE || bytes.includes(0)) return null;
  const text = bytes.toString("utf8");
  return text.includes("\ufffd") ? null : { text, bytes: bytes.length };
}

router.post("/analyze", async (req, res) => {
  try {
    const input = AnalyzeRepositoryBody.parse(req.body);
    const repository = parseRepositoryUrl(input.repository_url);
    const metadata = await githubGet<{
      name?: string;
      full_name?: string;
      owner?: { login?: string };
      description?: string | null;
      html_url?: string;
      default_branch?: string;
      stargazers_count?: number;
      forks_count?: number;
      open_issues_count?: number;
      language?: string | null;
      size?: number;
      topics?: string[];
    }>(`/repos/${repository.owner}/${repository.name}`);
    const defaultBranch = metadata.default_branch || "main";
    const treePayload = await githubGet<{ truncated?: boolean; tree?: GitHubTreeEntry[] }>(
      `/repos/${repository.owner}/${repository.name}/git/trees/${encodeURIComponent(defaultBranch)}?recursive=1`,
    );
    const entries = treePayload.tree ?? [];
    const rawFiles = entries.filter((entry) => entry.type === "blob");
    const relevant = rawFiles
      .filter((entry) => isRelevantPath(entry.path))
      .sort(
        (left, right) =>
          filePriority(left.path) - filePriority(right.path) ||
          left.path.localeCompare(right.path),
      );
    const selected = relevant.slice(0, MAX_FILES);
    let skipped = rawFiles.length - relevant.length + (relevant.length - selected.length);
    let downloadedSize = 0;
    const languageCounts: Record<string, number> = {};
    const files: Array<{
      path: string;
      size: number;
      type: "file";
      language: string | null;
      skipped: boolean;
      skip_reason: string | null;
    }> = [];

    for (const entry of selected) {
      const size = Math.max(0, entry.size ?? 0);
      const language = detectLanguage(entry.path);
      let skippedReason: string | null = null;
      if (size > MAX_FILE_SIZE) {
        skippedReason = "File exceeds the 200 KB file-size limit.";
      } else if (downloadedSize + size > MAX_TOTAL_SOURCE_SIZE) {
        skippedReason = "Total source-size limit reached.";
      } else {
        try {
          const file = await fetchFileText(
            repository.owner,
            repository.name,
            entry.path,
            defaultBranch,
          );
          if (!file) {
            skippedReason = "File contents were unavailable or not valid text.";
          } else {
            downloadedSize += file.bytes;
            if (language) languageCounts[language] = (languageCounts[language] ?? 0) + 1;
          }
        } catch {
          skippedReason = "File contents were unavailable or not valid text.";
        }
      }
      if (skippedReason) skipped += 1;
      files.push({
        path: entry.path,
        size,
        type: "file",
        language,
        skipped: Boolean(skippedReason),
        skip_reason: skippedReason,
      });
    }

    const truncated = Boolean(treePayload.truncated) || relevant.length > MAX_FILES;
    const responseBody = AnalyzeRepositoryResponse.parse({
      repository: {
        url: repository.url,
        owner: metadata.owner?.login || repository.owner,
        name: metadata.name || repository.name,
        description: metadata.description ?? null,
        default_branch: defaultBranch,
        stars: metadata.stargazers_count ?? 0,
        forks: metadata.forks_count ?? 0,
        open_issues: metadata.open_issues_count ?? 0,
        language: metadata.language ?? null,
        size_kb: metadata.size ?? 0,
        topics: metadata.topics ?? [],
      },
      overall_score: null,
      category_scores: [
        "repository structure",
        "documentation",
        "engineering practices",
        "maintenance signals",
      ].map((category) => ({ category, score: null, status: "not_started" })),
      summary: `Collected ${files.filter((file) => !file.skipped).length} text files from ${repository.owner}/${repository.name} without cloning it.${skipped ? ` ${skipped} files were skipped safely.` : ""}`,
      findings: [],
      recommendations: [
        "Use the collected repository snapshot as input for the next analyzer phase.",
        "Keep evidence collection read-only; no repository code is executed.",
      ],
      phase: "Phase 2 — repository ingestion",
      statistics: {
        total_files_found: rawFiles.length,
        files_analyzed: files.filter((file) => !file.skipped).length,
        files_skipped: skipped,
        total_source_size: downloadedSize,
        truncated,
        truncation_reason: treePayload.truncated
          ? "GitHub truncated the repository tree response."
          : relevant.length > MAX_FILES
            ? `Only the first ${MAX_FILES} relevant files were selected.`
            : null,
      },
      languages: languageCounts,
      files,
    });
    res.json(responseBody);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request.";
    const responseStatus =
      error instanceof GitHubRequestError ? error.status : 400;
    res.status(responseStatus).json({ error: message });
  }
});

export default router;