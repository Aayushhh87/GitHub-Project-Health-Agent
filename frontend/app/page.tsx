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
          <span className="phase-chip">PHASE 3 / QUALITY + SECURITY</span>
      </header>

      <section className="hero">
        <p className="eyebrow">Evidence before opinion</p>
        <h1>See how healthy a project really is.</h1>
        <p className="hero-copy">
          Enter a public GitHub repository to collect its metadata, structure, and
          deterministic quality and security findings without executing anything locally.
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
            <span className="status-badge">Read complete</span>
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
                <strong>—</strong>
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
          <div className="next-step">
            <span className="step-index">01</span>
            <div>
              <strong>Static analysis complete</strong>
              <p>
                The next phase can now analyze this structured snapshot for
                quality, security, and maintenance signals.
              </p>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
