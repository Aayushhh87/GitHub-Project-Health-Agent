"use client";

import { FormEvent, useState } from "react";

import { analyzeRepository } from "../lib/api";
import type { HealthReport } from "../types/report";

const examples = [
  "https://github.com/torvalds/linux",
  "https://github.com/vercel/next.js",
];

export default function Home() {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [report, setReport] = useState<HealthReport | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setReport(null);
    setIsLoading(true);
    try {
      setReport(await analyzeRepository(repositoryUrl));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Something went wrong.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            GH
          </span>
          <span>Project Health Agent</span>
        </div>
          <span className="phase-chip">PHASE 5 / AI + SCORING</span>
      </header>

      <section className="hero">
        <p className="eyebrow">Evidence before opinion</p>
        <h1>See how healthy a project really is.</h1>
        <p className="hero-copy">
          Enter a public GitHub repository to collect its metadata, structure, and
          deterministic quality, security, dependency, and test evidence without
          executing anything locally.
        </p>

        <form className="analyze-form" onSubmit={handleSubmit}>
          <label htmlFor="repository-url">GitHub repository URL</label>
          <div className="input-row">
            <input
              id="repository-url"
              type="url"
              value={repositoryUrl}
              onChange={(event) => setRepositoryUrl(event.target.value)}
              placeholder="https://github.com/owner/repository"
              required
            />
            <button type="submit" disabled={isLoading}>
              {isLoading ? "Reading repository…" : "Analyze repository"}
            </button>
          </div>
          <div className="form-footer">
            <span>Public repositories only</span>
            <span>Nothing is cloned locally</span>
          </div>
        </form>

        <div className="examples" aria-label="Example repositories">
          <span>Try an example</span>
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setRepositoryUrl(example)}
            >
              {example.replace("https://github.com/", "")}
            </button>
          ))}
        </div>
      </section>

      {error && <p className="error-message" role="alert">{error}</p>}

      {report && (
        <section className="report" aria-live="polite">
          <div className="report-heading">
            <div>
              <p className="eyebrow">Repository snapshot</p>
              <h2>
                {report.repository.owner}/{report.repository.name}
              </h2>
            </div>
            <span className="status-badge">
              {report.overall_score != null
                ? `Score ${report.overall_score}`
                : "Read complete"}
            </span>
          </div>
          <p className="report-summary">{report.summary}</p>
          {report.repository.description && (
            <p className="report-description">{report.repository.description}</p>
          )}
          <div className="repository-meta">
            <span>★ {report.repository.stars.toLocaleString()} stars</span>
            <span>⑂ {report.repository.forks.toLocaleString()} forks</span>
            <span>Branch: {report.repository.default_branch}</span>
          </div>
          <div className="stats-grid">
            <article className="stat">
              <span>Total files</span>
              <strong>{report.statistics.total_files_found.toLocaleString()}</strong>
            </article>
            <article className="stat">
              <span>Analyzed</span>
              <strong>{report.statistics.files_analyzed.toLocaleString()}</strong>
            </article>
            <article className="stat">
              <span>Skipped</span>
              <strong>{report.statistics.files_skipped.toLocaleString()}</strong>
            </article>
            <article className="stat">
              <span>Source size</span>
              <strong>
                {Math.round(
                  report.statistics.total_source_size / 1024,
                ).toLocaleString()}{" "}
                KB
              </strong>
            </article>
          </div>
          <div className="evidence-columns">
            <div>
              <h3>Detected languages</h3>
              {Object.keys(report.languages).length > 0 ? (
                <ul className="language-list">
                  {Object.entries(report.languages).map(([language, count]) => (
                    <li key={language}>
                      <span>{language}</span>
                      <strong>{count}</strong>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No recognized source extensions found.</p>
              )}
            </div>
            <div>
              <h3>Analyzed file paths</h3>
              {report.files.filter((file) => !file.skipped).length > 0 ? (
                <ul className="file-list">
                  {report.files
                    .filter((file) => !file.skipped)
                    .map((file) => (
                      <li key={file.path}>{file.path}</li>
                    ))}
                </ul>
              ) : (
                <p className="muted">No files were available for analysis.</p>
              )}
            </div>
          </div>
          <div className="category-grid">
            {report.category_scores.map((category) => (
              <article className="category" key={category.category}>
                <span>{category.category}</span>
                <strong>
                  {category.score != null ? category.score : "—"}
                </strong>
                <small>{category.status.replace("_", " ")}</small>
              </article>
            ))}
          </div>
          <div className="findings">
            <div className="findings-heading">
              <h3>Quality and security findings</h3>
              <span>{report.findings.length} detected</span>
            </div>
            {report.findings.length > 0 ? (
              <ul className="finding-list">
                {report.findings.map((finding, index) => (
                  <li key={`${finding.title}-${finding.file}-${finding.line}-${index}`}>
                    <div className="finding-title">
                      <strong>{finding.title}</strong>
                      <span className={`severity severity-${finding.severity}`}>
                        {finding.severity}
                      </span>
                    </div>
                    <p>{finding.category}{finding.file ? ` · ${finding.file}` : ""}{finding.line ? `:${finding.line}` : ""}</p>
                    <p>{finding.description}</p>
                    {finding.evidence.map((evidence) => (
                      <code key={evidence}>{evidence}</code>
                    ))}
                    {finding.recommendation && <small>{finding.recommendation}</small>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No quality or security findings were detected.</p>
            )}
          </div>
          <div className="analysis-metadata">
            <article>
              <h3>Dependencies</h3>
              <p>
                {report.dependencies.has_dependency_management
                  ? `${report.dependencies.dependency_count ?? "Unknown"} dependencies across ${report.dependencies.ecosystems.join(", ")}.`
                  : "No supported dependency management detected."}
              </p>
              <small>
                Manifests: {report.dependencies.manifests.join(", ") || "none"}
                <br />
                Lockfiles: {report.dependencies.lockfiles.join(", ") || "none"}
              </small>
            </article>
            <article>
              <h3>Automated tests</h3>
              <p>
                {report.testing.tests_detected
                  ? `${report.testing.test_file_count} test file${report.testing.test_file_count === 1 ? "" : "s"} detected.`
                  : "No automated tests detected."}
              </p>
              <small>
                Frameworks: {report.testing.frameworks.join(", ") || "none detected"}
                <br />
                Directories: {report.testing.test_directories.join(", ") || "none detected"}
              </small>
            </article>
          </div>
          {(report.strengths?.length ||
            report.weaknesses?.length ||
            report.architecture_insight ||
            report.documentation_insight) && (
            <div className="analysis-metadata">
              {report.strengths && report.strengths.length > 0 && (
                <article>
                  <h3>Strengths</h3>
                  <ul>
                    {report.strengths.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              )}
              {report.weaknesses && report.weaknesses.length > 0 && (
                <article>
                  <h3>Weaknesses</h3>
                  <ul>
                    {report.weaknesses.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              )}
              {report.architecture_insight && (
                <article>
                  <h3>Architecture insight</h3>
                  <p>{report.architecture_insight}</p>
                </article>
              )}
              {report.documentation_insight && (
                <article>
                  <h3>Documentation insight</h3>
                  <p>{report.documentation_insight}</p>
                </article>
              )}
            </div>
          )}
          {report.recommendations.length > 0 && (
            <div className="findings">
              <div className="findings-heading">
                <h3>Recommendations</h3>
              </div>
              <ul className="finding-list">
                {report.recommendations.map((item) => (
                  <li key={item}>
                    <p>{item}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="next-step">
            <span className="step-index">01</span>
            <div>
              <strong>
                {report.ai_enabled
                  ? "AI synthesis and scoring complete"
                  : "Deterministic scoring complete"}
              </strong>
              <p>
                Category scores are calculated from severity-weighted findings.
                Architecture insight does not affect the overall score.
                {report.ai_enabled
                  ? ""
                  : " Set OPENROUTER_API_KEY to enable AI narrative synthesis."}
              </p>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
