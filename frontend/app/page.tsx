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
        <span className="phase-chip">PHASE 1 / FOUNDATION</span>
      </header>

      <section className="hero">
        <p className="eyebrow">Evidence before opinion</p>
        <h1>See how healthy a project really is.</h1>
        <p className="hero-copy">
          Enter a public GitHub repository to prepare an evidence-driven health
          report. This first foundation validates the project and establishes
          the report contract for deeper analysis.
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
              {isLoading ? "Preparing…" : "Analyze repository"}
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
              <p className="eyebrow">Repository accepted</p>
              <h2>
                {report.repository.owner}/{report.repository.name}
              </h2>
            </div>
            <span className="status-badge">Ready for evidence</span>
          </div>
          <p className="report-summary">{report.summary}</p>
          <div className="category-grid">
            {report.category_scores.map((category) => (
              <article className="category" key={category.category}>
                <span>{category.category}</span>
                <strong>—</strong>
                <small>{category.status.replace("_", " ")}</small>
              </article>
            ))}
          </div>
          <div className="next-step">
            <span className="step-index">01</span>
            <div>
              <strong>Foundation complete</strong>
              <p>
                The next phase will collect repository metadata, tree structure,
                and file evidence through the GitHub REST API.
              </p>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
