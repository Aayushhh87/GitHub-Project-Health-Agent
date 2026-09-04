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

type PreviewFinding = {
  title: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
  description: string;
  evidence: string[];
  category: string;
  file: string;
  line: number;
  recommendation: string;
};

type PreviewSource = {
  path: string;
  language: string | null;
  content: string;
};

type PreviewDependencies = {
  has_dependency_management: boolean;
  ecosystems: string[];
  manifests: string[];
  lockfiles: string[];
  dependency_count: number | null;
  production_dependencies: number | null;
  development_dependencies: number | null;
  pinned_dependencies: number | null;
  loose_dependencies: number | null;
};

type PreviewTesting = {
  tests_detected: boolean;
  test_file_count: number;
  test_directories: string[];
  frameworks: string[];
  evidence_files: string[];
};

const previewManifestEcosystems: Record<string, string> = {
  "requirements.txt": "Python",
  "requirements-dev.txt": "Python",
  "pyproject.toml": "Python",
  "pipfile": "Python",
  "setup.py": "Python",
  "setup.cfg": "Python",
  "package.json": "JavaScript/TypeScript",
  "pom.xml": "Java",
  "build.gradle": "Java",
  "build.gradle.kts": "Java",
  "go.mod": "Go",
  "cargo.toml": "Rust",
  "composer.json": "PHP",
};

const previewLockfileEcosystems: Record<string, string> = {
  "package-lock.json": "JavaScript/TypeScript",
  "npm-shrinkwrap.json": "JavaScript/TypeScript",
  "yarn.lock": "JavaScript/TypeScript",
  "pnpm-lock.yaml": "JavaScript/TypeScript",
  "pipfile.lock": "Python",
  "poetry.lock": "Python",
  "go.sum": "Go",
  "cargo.lock": "Rust",
  "composer.lock": "PHP",
};

function maskPreviewSecret(value: string) {
  return `${value.slice(0, 4)}********`;
}

function previewFindings(path: string, language: string | null, text: string): PreviewFinding[] {
  const findings: PreviewFinding[] = [];
  const lines = text.split(/\r?\n/);
  const secretPattern = /\b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b/;
  const assignmentPattern = /\b(api[_-]?key|token|password|passwd|secret|private[_-]?key)\s*[:=]\s*(['"])([^'"\r\n]{8,})\2/i;
  lines.forEach((line, index) => {
    const lineNumber = index + 1;
    const secret = line.match(secretPattern);
    const assignment = line.match(assignmentPattern);
    if (secret || assignment) {
      const value = secret?.[0] ?? assignment?.[3] ?? "";
      if (!["changeme", "placeholder", "your-key-here"].includes(value.toLowerCase())) {
        findings.push({
          title: "Likely hardcoded credential",
          severity: "high",
          description: "A token-shaped or secret-like literal appears in repository text.",
          evidence: [`Possible credential detected: ${maskPreviewSecret(value)}`],
          category: "Security",
          file: path,
          line: lineNumber,
          recommendation: "Rotate the value if real and load it from environment or secret storage.",
        });
      }
    }
    if (/\b(?:eval|exec)\s*\(/.test(line)) {
      findings.push({
        title: "Dynamic code execution",
        severity: "high",
        description: "The source invokes eval or exec.",
        evidence: [line.trim().slice(0, 240)],
        category: "Security",
        file: path,
        line: lineNumber,
        recommendation: "Avoid dynamic execution and use a constrained parser or explicit dispatch.",
      });
    }
    if (/\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\([^)\n]*\bshell\s*=\s*True/i.test(line)) {
      findings.push({
        title: "Shell execution through subprocess",
        severity: "high",
        description: "A subprocess call enables shell interpretation.",
        evidence: [line.trim().slice(0, 240)],
        category: "Security",
        file: path,
        line: lineNumber,
        recommendation: "Pass an argument list without shell=True and validate external input.",
      });
    }
    if (/\bpickle\.(?:load|loads)\s*\(/.test(line)) {
      findings.push({
        title: "Unsafe pickle deserialization",
        severity: "high",
        description: "Pickle deserialization can execute attacker-controlled object behavior.",
        evidence: [line.trim().slice(0, 240)],
        category: "Security",
        file: path,
        line: lineNumber,
        recommendation: "Use a data-only serialization format and validate untrusted input.",
      });
    }
    if (/\bverify\s*=\s*False\b/i.test(line)) {
      findings.push({
        title: "TLS certificate verification disabled",
        severity: "medium",
        description: "An HTTP client disables certificate verification.",
        evidence: [line.trim().slice(0, 240)],
        category: "Security",
        file: path,
        line: lineNumber,
        recommendation: "Keep TLS verification enabled.",
      });
    }
    const todo = line.match(/\b(TODO|FIXME)\b(?:\s*[:\-]\s*)?(.*)/i);
    if (todo) {
      findings.push({
        title: `${todo[1].toUpperCase()} comment in source`,
        severity: "low",
        description: "The file contains an explicit unfinished-work marker.",
        evidence: [`${todo[1].toUpperCase()}: ${(todo[2] || "follow-up work").slice(0, 160)}`],
        category: "Code Quality",
        file: path,
        line: lineNumber,
        recommendation: "Resolve the item or track it in the project issue system.",
      });
    }
    if ((language === "JavaScript" || language === "TypeScript") && /\b(?:console\.(?:log|debug|trace)|debugger)\b/.test(line)) {
      findings.push({
        title: "Debug statement in source",
        severity: "low",
        description: "A console or debugger statement is present in source.",
        evidence: [line.trim().slice(0, 240)],
        category: "Code Quality",
        file: path,
        line: lineNumber,
        recommendation: "Remove debug output or route intentional diagnostics through the project logger.",
      });
    }
  });
  return findings;
}

function previewDependencyData(sources: PreviewSource[]): {
  data: PreviewDependencies;
  findings: PreviewFinding[];
} {
  const manifests = sources.filter((source) => previewManifestEcosystems[source.path.split("/").at(-1)?.toLowerCase() ?? ""]);
  const locks = sources.filter((source) => previewLockfileEcosystems[source.path.split("/").at(-1)?.toLowerCase() ?? ""]);
  const ecosystems = [...new Set([
    ...manifests.map((source) => previewManifestEcosystems[source.path.split("/").at(-1)?.toLowerCase() ?? ""]),
    ...locks.map((source) => previewLockfileEcosystems[source.path.split("/").at(-1)?.toLowerCase() ?? ""]),
  ])].sort();
  let dependencyCount = 0;
  let productionCount = 0;
  let developmentCount = 0;
  let pinnedCount = 0;
  let looseCount = 0;
  let parsed = false;
  const findings: PreviewFinding[] = [];
  const add = (version: string, development = false) => {
    dependencyCount += 1;
    if (development) developmentCount += 1;
    else productionCount += 1;
    if (/^(?:v?\d+\.){2}\d+(?:[-+][\w.-]+)?$/.test(version.replace(/^==+/, "").trim())) pinnedCount += 1;
    else looseCount += 1;
    parsed = true;
  };
  const addRequirements = (content: string, development: boolean) => {
    content.split(/\r?\n/).forEach((line) => {
      const value = line.split("#")[0].trim();
      if (!value || value.startsWith("-")) return;
      const match = value.match(/^([A-Za-z0-9_.-]+)(.*)$/);
      if (match) add(match[2].trim(), development);
    });
  };

  manifests.forEach((source) => {
    const name = source.path.split("/").at(-1)?.toLowerCase() ?? "";
    try {
      if (name === "requirements.txt" || name === "requirements-dev.txt") {
        addRequirements(source.content, name.endsWith("-dev.txt"));
      } else if (name === "package.json" || name === "composer.json") {
        const json = JSON.parse(source.content) as Record<string, unknown>;
        const sections = name === "package.json"
          ? [["dependencies", false], ["optionalDependencies", false], ["peerDependencies", false], ["devDependencies", true]]
          : [["require", false], ["require-dev", true]];
        sections.forEach(([section, development]) => {
          const values = json[section as string];
          if (values && typeof values === "object") {
            Object.values(values as Record<string, unknown>).forEach((version) => add(String(version), Boolean(development)));
          }
        });
      } else if (name === "pom.xml") {
        [...source.content.matchAll(/<dependency>([\s\S]*?)<\/dependency>/gi)].forEach((match) => {
          add(match[1].match(/<version>\s*([^<]+)/i)?.[1]?.trim() ?? "");
        });
      } else if (name === "go.mod") {
        source.content.split(/\r?\n/).forEach((line) => {
          const match = line.trim().match(/^(?:\S+)\s+(v\d[^\s]+)/);
          if (match) add(match[1]);
        });
      } else if (name === "cargo.toml") {
        [...source.content.matchAll(/^\s*([A-Za-z0-9_-]+)\s*=\s*["']([^"']+)["']/gm)].forEach((match) => {
          add(match[2], /dev-dependencies/.test(source.content.slice(0, match.index ?? 0)));
        });
      } else if (name === "pyproject.toml") {
        const dependencyLines = source.content.match(/(?:dependencies|optional-dependencies)[\s\S]*?(?=^\[|\Z)/gim) ?? [];
        dependencyLines.forEach((block) => addRequirements(block, /optional-dependencies/i.test(block)));
      } else if (name === "setup.py" || name === "setup.cfg") {
        const lines = source.content.split(/\r?\n/).filter((line) => /install_requires|extras_require|^\s+[A-Za-z0-9_.-]+(?:==|>=|<=|~=)/.test(line));
        lines.forEach((line) => addRequirements(line.replace(/.*(?:install_requires|extras_require)\s*=?\s*/, ""), /extras_require/.test(line)));
      }
    } catch {
      findings.push({
        title: "Malformed dependency manifest",
        severity: "medium",
        description: "A dependency manifest was fetched but could not be parsed safely.",
        evidence: ["Dependency metadata was skipped for this file."],
        category: "Dependencies",
        file: source.path,
        line: 1,
        recommendation: "Fix the manifest syntax so dependency tooling can read it reliably.",
      });
    }
  });

  if (!manifests.length && !locks.length) {
    findings.push({
      title: "No dependency manifest detected",
      severity: "info",
      description: "No supported dependency manifest or lockfile was found in the analyzed files.",
      evidence: ["Checked the supported dependency filenames in the fetched repository evidence."],
      category: "Dependencies",
      file: "",
      line: 1,
      recommendation: "No action is needed if this repository intentionally has no external dependencies.",
    });
  }
  if (looseCount > 0) {
    findings.push({
      title: "Broad dependency version specification",
      severity: "low",
      description: `${looseCount} dependency specification(s) are not pinned to an exact version.`,
      evidence: [`Pinned: ${pinnedCount}; loose or range-based: ${looseCount}.`],
      category: "Dependencies",
      file: manifests[0]?.path ?? locks[0]?.path ?? "",
      line: 1,
      recommendation: "Use deliberate version ranges or exact pins and review updates through a controlled workflow.",
    });
  }
  const nodeManifest = manifests.find((source) => previewManifestEcosystems[source.path.split("/").at(-1)?.toLowerCase() ?? ""] === "JavaScript/TypeScript");
  if (nodeManifest && !locks.some((source) => previewLockfileEcosystems[source.path.split("/").at(-1)?.toLowerCase() ?? ""] === "JavaScript/TypeScript")) {
    findings.push({
      title: "Dependency manifest has no lockfile",
      severity: "low",
      description: "JavaScript/TypeScript dependency metadata is present without a recognized lockfile.",
      evidence: ["No package-lock.json, npm-shrinkwrap.json, yarn.lock, or pnpm-lock.yaml was fetched."],
      category: "Dependencies",
      file: nodeManifest.path,
      line: 1,
      recommendation: "Commit a lockfile when the project workflow supports reproducible installs.",
    });
  }
  return {
    data: {
      has_dependency_management: Boolean(manifests.length || locks.length),
      ecosystems,
      manifests: manifests.map((source) => source.path).sort(),
      lockfiles: locks.map((source) => source.path).sort(),
      dependency_count: parsed ? dependencyCount : null,
      production_dependencies: parsed ? productionCount : null,
      development_dependencies: parsed ? developmentCount : null,
      pinned_dependencies: parsed ? pinnedCount : null,
      loose_dependencies: parsed ? looseCount : null,
    },
    findings,
  };
}

function previewTestingData(sources: PreviewSource[]): {
  data: PreviewTesting;
  findings: PreviewFinding[];
} {
  const testFiles = sources.filter((source) => {
    const name = source.path.split("/").at(-1) ?? "";
    return /(^test_[^/]+\.py$|^[^/]+_test\.py$|\.(?:test|spec)\.(?:js|jsx|ts|tsx)$|_test\.go$|Test\.java$)/i.test(name);
  });
  const directories = [...new Set(sources.flatMap((source) => {
    const parts = source.path.split("/");
    return parts.slice(0, -1).flatMap((_, index) => {
      const part = parts[index].toLowerCase();
      return ["test", "tests", "__tests__", "spec"].includes(part) ? [parts.slice(0, index + 1).join("/")] : [];
    });
  }))].sort();
  const frameworks = new Set<string>();
  const evidence = new Set<string>(testFiles.map((source) => source.path));
  sources.forEach((source) => {
    const lower = source.content.toLowerCase();
    const name = source.path.split("/").at(-1)?.toLowerCase() ?? "";
    if (lower.includes("pytest") || name === "pytest.ini" || name === "tox.ini") { frameworks.add("pytest"); evidence.add(source.path); }
    if (lower.includes("jest") || name.startsWith("jest.config")) { frameworks.add("Jest"); evidence.add(source.path); }
    if (lower.includes("vitest") || name.startsWith("vitest.config")) { frameworks.add("Vitest"); evidence.add(source.path); }
    if (lower.includes("mocha") || name.startsWith(".mocharc")) { frameworks.add("Mocha"); evidence.add(source.path); }
    if (lower.includes("junit") || lower.includes("org.junit")) { frameworks.add("JUnit"); evidence.add(source.path); }
    if (/\b(?:import|from)\s+unittest\b/.test(source.content)) { frameworks.add("unittest"); evidence.add(source.path); }
    if (source.path.endsWith("_test.go")) frameworks.add("Go testing");
    if (source.content.includes("#[cfg(test)]") || /\bmod\s+tests\b/.test(source.content)) { frameworks.add("Rust test"); evidence.add(source.path); }
  });
  const detected = Boolean(testFiles.length || directories.length || frameworks.size);
  const findings: PreviewFinding[] = detected ? [] : [{
    title: "No automated tests detected",
    severity: "medium",
    description: "No common automated test files, directories, or framework configuration were found.",
    evidence: ["Test detection checked common naming conventions and framework markers."],
    category: "Testing",
    file: "",
    line: 1,
    recommendation: "Add automated tests appropriate to the project's runtime and critical behavior.",
  }];
  return {
    data: {
      tests_detected: detected,
      test_file_count: testFiles.length,
      test_directories: directories,
      frameworks: [...frameworks].sort(),
      evidence_files: [...evidence].sort(),
    },
    findings,
  };
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
    const findings: PreviewFinding[] = [];
    const analyzedSources: PreviewSource[] = [];
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
            analyzedSources.push({ path: entry.path, language, content: file.text });
            findings.push(...previewFindings(entry.path, language, file.text));
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
    const dependencyResult = previewDependencyData(analyzedSources);
    const testingResult = previewTestingData(analyzedSources);
    findings.push(...dependencyResult.findings, ...testingResult.findings);
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
      findings,
      recommendations: [
        "Review each quality and security signal with its file and line evidence.",
        "Keep analysis read-only; repository code is never executed.",
      ],
      phase: "Phase 4 — dependency analysis and test detection",
      dependencies: dependencyResult.data,
      testing: testingResult.data,
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
      stats: {
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