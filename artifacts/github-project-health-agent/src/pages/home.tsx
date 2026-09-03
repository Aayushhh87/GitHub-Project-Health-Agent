import { useState } from 'react';
import type { FormEvent } from 'react';
import type { CSSProperties } from 'react';
import {
  Activity,
  ArrowUpRight,
  Check,
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  ClipboardCheck,
  ExternalLink,
  Github,
  LoaderCircle,
  Radar,
  RotateCcw,
  Search,
  ShieldCheck,
  Terminal,
} from 'lucide-react';
import type { HealthReport } from '@workspace/api-client-react';
import {
  getHealthCheckQueryKey,
  useAnalyzeRepository,
  useHealthCheck,
} from '@workspace/api-client-react';

type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';

const severityMeta: Record<Severity, { label: string; className: string }> = {
  info: { label: 'Informational', className: 'bg-[#e4e9f2] text-[#2f3877]' },
  low: { label: 'Low', className: 'bg-[#e7efd7] text-[#46631e]' },
  medium: { label: 'Medium', className: 'bg-[#f5e5c5] text-[#7a4c16]' },
  high: { label: 'High', className: 'bg-[#f6d8cc] text-[#943f2e]' },
  critical: { label: 'Critical', className: 'bg-[#f3c9cb] text-[#8e2633]' },
};

function isGithubUrl(value: string) {
  try {
    const url = new URL(value);
    return url.hostname === 'github.com' && url.pathname.split('/').filter(Boolean).length >= 2;
  } catch {
    return false;
  }
}

function HealthPill() {
  const { data, isLoading, isError } = useHealthCheck({
    query: {
      queryKey: getHealthCheckQueryKey(),
      staleTime: 30000,
    },
  });

  const isOnline = !isLoading && !isError && data?.status;

  return (
    <div
      className="mt-auto flex items-center gap-2 border-t border-white/10 pt-5 text-[11px] text-[#b1b6c6]"
      data-testid="status-api-health"
    >
      <span className={`relative flex h-2 w-2 rounded-full ${isOnline ? 'bg-[#cbe24b]' : isLoading ? 'bg-[#d5bb67]' : 'bg-[#e36d5e]'}`}>
        {isOnline && <span className="absolute inset-0 animate-ping rounded-full bg-[#cbe24b] opacity-50" />}
      </span>
      <span>{isLoading ? 'Checking API connection' : isError ? 'API connection unavailable' : 'API connection ready'}</span>
    </div>
  );
}

function Rail() {
  return (
    <aside className="side-rail flex flex-col px-6 py-7" data-testid="navigation-sidebar">
      <div className="relative z-10">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[#cbe24b] text-[#242849] shadow-[0_6px_18px_rgba(203,226,75,0.16)]">
            <Radar size={19} strokeWidth={2.4} />
          </div>
          <div>
            <p className="font-[var(--app-font-serif)] text-[15px] font-bold tracking-[-0.03em] text-[#fbf8ef]">Health Agent</p>
            <p className="mono-label mt-0.5 text-[9px] text-[#8990aa]">GitHub project health</p>
          </div>
        </div>

        <div className="mt-14">
          <p className="mono-label mb-3 text-[#7f86a2]">Workspace</p>
          <div className="flex items-center gap-3 rounded-md bg-white/[0.09] px-3 py-3 text-sm text-[#fbf8ef]">
            <Activity size={16} className="text-[#cbe24b]" />
            <span>Repository read</span>
            <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#cbe24b]" />
          </div>
        </div>

        <div className="mt-9 border-l border-[#cbe24b]/40 pl-4">
          <p className="mono-label text-[#cbe24b]">Phase 01</p>
          <p className="mt-2 text-[13px] leading-5 text-[#d0d3df]">Evidence-first baseline</p>
          <p className="mt-2 text-[11px] leading-5 text-[#8990aa]">
            Start with the public signals. Decide what deserves a deeper look.
          </p>
        </div>
      </div>
      <HealthPill />
    </aside>
  );
}

function ScoreRing({ score }: { score: number | null }) {
  const displayScore = score === null ? '—' : Math.round(score);
  const percentage = score === null ? 0 : Math.max(0, Math.min(100, score));

  return (
    <div
      className="score-ring relative flex h-[142px] w-[142px] shrink-0 items-center justify-center rounded-full"
      style={{ '--score': `${percentage}%` } as CSSProperties}
      data-testid="metric-overall-score"
    >
      <div className="relative z-10 text-center">
        <p className="font-[var(--app-font-serif)] text-[47px] font-bold leading-none tracking-[-0.08em] text-[#2f3877]" data-testid="text-overall-score">
          {displayScore}
        </p>
        <p className="mono-label mt-2 text-[9px] text-[#747681]">overall / 100</p>
      </div>
    </div>
  );
}

function CategoryCard({ category, score, status, index }: { category: string; score: number | null; status: string; index: number }) {
  const complete = status === 'complete';
  const pending = status === 'pending';
  const value = score === null ? null : Math.round(score);

  return (
    <div className={`stagger-in stagger-${Math.min(index + 1, 4)} border-t border-[#ddd9ca] pt-4`} data-testid={`card-category-${index}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-[#292b40]">{category}</p>
        {complete ? (
          <CheckCircle2 size={17} className="text-[#69852c]" />
        ) : pending ? (
          <LoaderCircle size={16} className="animate-spin text-[#bd8c3b]" />
        ) : (
          <CircleDashed size={17} className="text-[#9b9b98]" />
        )}
      </div>
      <div className="mt-5 flex items-end justify-between">
        <span className="font-[var(--app-font-mono)] text-2xl font-medium tracking-[-0.08em] text-[#2f3877]" data-testid={`text-category-score-${index}`}>
          {value === null ? '—' : value}
        </span>
        <span className="mono-label text-[9px] text-[#898982]">{complete ? 'measured' : pending ? 'in progress' : 'not started'}</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#e6e3d7]">
        <div className="h-full rounded-full bg-[#cbe24b] transition-[width] duration-500" style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}

function ReportView({ report }: { report: HealthReport }) {
  return (
    <section className="report-in mt-16 pb-20" data-testid="section-health-report">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mono-label text-[#73756f]">Analysis report / {report.phase}</p>
          <h2 className="display-type mt-2 text-4xl font-bold text-[#292b40] sm:text-5xl" data-testid="text-report-title">
            The first read.
          </h2>
        </div>
        <a
          href={report.repository.url}
          target="_blank"
          rel="noreferrer"
          className="group flex items-center gap-2 border-b border-[#b9b6aa] pb-1 text-sm font-semibold text-[#2f3877] transition-colors hover:border-[#2f3877]"
          data-testid="link-repository"
        >
          <Github size={15} />
          <span data-testid="text-repository-name">{report.repository.owner}/{report.repository.name}</span>
          <ArrowUpRight size={14} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </a>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.05fr_1.95fr]">
        <div className="panel rounded-[3px] p-6 sm:p-8">
          <div className="flex flex-wrap items-center gap-7">
            <ScoreRing score={report.overall_score} />
            <div className="min-w-[180px] flex-1">
              <div className="flex items-center gap-2 text-[#69852c]">
                <ShieldCheck size={17} />
                <span className="mono-label text-[10px]">Phase 1 complete</span>
              </div>
              <p className="mt-3 max-w-[275px] text-[15px] leading-6 text-[#51525c]" data-testid="text-summary">
                {report.summary}
              </p>
            </div>
          </div>
          <div className="mt-8 flex items-center gap-2 border-t border-[#e2dfd3] pt-4 text-[11px] text-[#777871]">
            <ClipboardCheck size={14} />
            <span>Scores reflect available public evidence only.</span>
          </div>
        </div>

        <div className="panel rounded-[3px] p-6 sm:p-8">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="mono-label text-[#73756f]">Signal map</p>
              <h3 className="mt-1 text-lg font-bold tracking-[-0.03em] text-[#292b40]">Category coverage</h3>
            </div>
            <span className="rounded-full bg-[#eef1d3] px-2.5 py-1 font-[var(--app-font-mono)] text-[10px] text-[#52651f]" data-testid="status-category-coverage">
              {report.category_scores.filter((item) => item.status === 'complete').length}/{report.category_scores.length} ready
            </span>
          </div>
          <div className="grid gap-x-7 gap-y-6 sm:grid-cols-2">
            {report.category_scores.map((item, index) => (
              <CategoryCard key={`${item.category}-${index}`} {...item} index={index} />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1.45fr_0.85fr]">
        <div className="panel rounded-[3px] p-6 sm:p-8">
          <div className="mb-6 flex items-end justify-between gap-3">
            <div>
              <p className="mono-label text-[#73756f]">Observed signals</p>
              <h3 className="mt-1 text-lg font-bold tracking-[-0.03em] text-[#292b40]">Findings</h3>
            </div>
            <span className="font-[var(--app-font-mono)] text-xs text-[#8c8c83]" data-testid="text-findings-count">
              {report.findings.length.toString().padStart(2, '0')} items
            </span>
          </div>
          {report.findings.length > 0 ? (
            <div className="space-y-3">
              {report.findings.map((finding, index) => {
                const meta = severityMeta[finding.severity];
                return (
                  <article className="finding-row rounded-[3px] border border-[#e1ded3] p-4" key={`${finding.title}-${index}`} data-testid={`card-finding-${index}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h4 className="text-[14px] font-bold text-[#292b40]" data-testid={`text-finding-title-${index}`}>{finding.title}</h4>
                      <span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] ${meta.className}`} data-testid={`badge-finding-severity-${index}`}>
                        {meta.label}
                      </span>
                    </div>
                    <p className="mt-2 text-[13px] leading-5 text-[#62636a]" data-testid={`text-finding-description-${index}`}>{finding.description}</p>
                    {finding.evidence.length > 0 && (
                      <div className="mt-3 space-y-1.5 border-l-2 border-[#cbe24b] pl-3">
                        {finding.evidence.map((evidence, evidenceIndex) => (
                          <p className="font-[var(--app-font-mono)] text-[11px] leading-5 text-[#77786f]" key={`${evidence}-${evidenceIndex}`} data-testid={`text-evidence-${index}-${evidenceIndex}`}>
                            {evidence}
                          </p>
                        ))}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-[3px] border border-dashed border-[#d6d3c6] bg-[#faf9f2] p-5 text-sm text-[#76766f]" data-testid="empty-findings">
              <CircleAlert size={17} />
              No findings were returned in this phase.
            </div>
          )}
        </div>

        <div className="rounded-[3px] bg-[#2f3877] p-6 text-[#fbf8ef] sm:p-8">
          <div className="flex items-center justify-between">
            <div>
              <p className="mono-label text-[#cbe24b]">Suggested next moves</p>
              <h3 className="mt-1 text-lg font-bold tracking-[-0.03em]">Recommendations</h3>
            </div>
            <Terminal size={19} className="text-[#cbe24b]" />
          </div>
          {report.recommendations.length > 0 ? (
            <ol className="mt-7 space-y-5">
              {report.recommendations.map((recommendation, index) => (
                <li className="flex gap-3 border-t border-white/15 pt-4 text-[13px] leading-5 text-[#d9dbe4]" key={`${recommendation}-${index}`} data-testid={`item-recommendation-${index}`}>
                  <span className="font-[var(--app-font-mono)] text-[11px] text-[#cbe24b]">0{index + 1}</span>
                  <span>{recommendation}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-7 border-t border-white/15 pt-4 text-[13px] leading-5 text-[#bdc1d0]" data-testid="empty-recommendations">No recommendations were returned in this phase.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function ReportSkeleton() {
  return (
    <div className="mt-16 space-y-5" aria-label="Loading report" data-testid="loading-report">
      <div className="skeleton-line h-5 w-40 rounded-sm" />
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="panel flex min-h-[250px] items-center gap-7 rounded-[3px] p-8">
          <div className="skeleton-line h-32 w-32 shrink-0 rounded-full" />
          <div className="w-full space-y-3"><div className="skeleton-line h-3 w-28 rounded" /><div className="skeleton-line h-5 w-3/4 rounded" /><div className="skeleton-line h-3 w-full rounded" /></div>
        </div>
        <div className="panel min-h-[250px] rounded-[3px] p-8"><div className="skeleton-line h-4 w-40 rounded" /><div className="mt-8 grid grid-cols-2 gap-8"><div className="skeleton-line h-16 rounded" /><div className="skeleton-line h-16 rounded" /><div className="skeleton-line h-16 rounded" /><div className="skeleton-line h-16 rounded" /></div></div>
      </div>
    </div>
  );
}

export default function Home() {
  const [repositoryUrl, setRepositoryUrl] = useState('');
  const [formError, setFormError] = useState('');
  const [report, setReport] = useState<HealthReport | null>(null);
  const analyze = useAnalyzeRepository();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = repositoryUrl.trim();
    if (!trimmed) {
      setFormError('Add a public GitHub repository URL to begin.');
      return;
    }
    if (!isGithubUrl(trimmed)) {
      setFormError('Use a URL in the format github.com/owner/repository.');
      return;
    }
    setFormError('');
    setReport(null);
    analyze.mutate(
      { data: { repository_url: trimmed } },
      { onSuccess: (nextReport) => setReport(nextReport) },
    );
  }

  const mutationError = analyze.error as { error?: string } | null;

  return (
    <div className="app-shell">
      <Rail />
      <main className="main-stage">
        <div className="mx-auto max-w-[1240px] px-6 py-7 sm:px-10 sm:py-9 lg:px-14">
          <header className="flex items-center justify-between border-b border-[#dedbd0] pb-6">
            <div className="flex items-center gap-2 text-[#73756f]">
              <span className="mono-label text-[10px]">Developer tooling</span>
              <span className="h-1 w-1 rounded-full bg-[#c6c2b5]" />
              <span className="text-xs">Public repository analysis</span>
            </div>
            <div className="hidden items-center gap-2 text-[#73756f] sm:flex">
              <span className="mono-label text-[9px]">Read only</span>
              <ShieldCheck size={15} className="text-[#69852c]" />
            </div>
          </header>

          <section className="stagger-in relative pt-16 sm:pt-20">
            <div className="pointer-events-none absolute -right-8 top-10 hidden h-44 w-44 rounded-full border border-[#d9ddae] lg:block" />
            <div className="pointer-events-none absolute -right-1 top-[6.75rem] hidden h-24 w-24 rounded-full border border-[#d9ddae] lg:block" />
            <p className="mono-label text-[#6f793c]">01 / establish a baseline</p>
            <h1 className="display-type mt-5 max-w-3xl text-[3.4rem] font-bold leading-[0.97] text-[#292b40] sm:text-[5.7rem]" data-testid="text-page-title">
              Know what you&apos;re<br /><span className="text-[#2f3877]">walking into.</span>
            </h1>
            <p className="mt-7 max-w-xl text-[15px] leading-7 text-[#62636a] sm:text-base">
              A fast, evidence-driven first read on the health of a public GitHub project. Paste a repository, then see the signals before you invest the time.
            </p>

            <form className="panel mt-10 max-w-3xl rounded-[3px] p-2 sm:flex sm:items-center" onSubmit={handleSubmit} data-testid="form-analyze-repository">
              <div className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2">
                <Search size={18} className="shrink-0 text-[#767872]" />
                <label className="sr-only" htmlFor="repository-url">GitHub repository URL</label>
                <input
                  id="repository-url"
                  type="url"
                  value={repositoryUrl}
                  onChange={(event) => { setRepositoryUrl(event.target.value); setFormError(''); }}
                  placeholder="https://github.com/owner/repository"
                  className="url-input min-w-0 flex-1 border-0 bg-transparent px-0 py-2 text-sm text-[#292b40] placeholder:text-[#9b9b93] focus:border-0 focus:bg-transparent focus:shadow-none"
                  data-testid="input-repository-url"
                  aria-invalid={Boolean(formError)}
                />
              </div>
              <button
                type="submit"
                disabled={analyze.isPending}
                className="primary-action flex w-full items-center justify-center gap-2 rounded-[2px] bg-[#2f3877] px-5 py-3 text-sm font-bold text-[#fbf8ef] disabled:cursor-wait disabled:opacity-70 sm:w-auto"
                data-testid="button-run-analysis"
              >
                {analyze.isPending ? <LoaderCircle size={16} className="animate-spin" /> : <Radar size={16} />}
                {analyze.isPending ? 'Reading repository' : 'Run analysis'}
              </button>
            </form>
            {formError && <p className="mt-3 flex items-center gap-2 text-xs font-semibold text-[#a14435]" role="alert" data-testid="status-form-error"><CircleAlert size={14} />{formError}</p>}
            {analyze.isError && !formError && (
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs font-semibold text-[#a14435]" role="alert" data-testid="status-analysis-error">
                <CircleAlert size={14} />
                <span>{mutationError?.error ?? 'The repository could not be analyzed. Check the URL and try again.'}</span>
                <button type="button" className="inline-flex items-center gap-1 border-b border-[#a14435] pb-0.5" onClick={() => { setFormError(''); document.querySelector<HTMLFormElement>('[data-testid="form-analyze-repository"]')?.requestSubmit(); }} data-testid="button-retry-analysis">
                  <RotateCcw size={12} /> Retry
                </button>
              </div>
            )}
            <p className="mt-3 flex items-center gap-2 text-[11px] text-[#8a8a82]"><ExternalLink size={12} /> Public repositories only. No credentials required.</p>
          </section>

          {analyze.isPending ? <ReportSkeleton /> : report ? <ReportView report={report} /> : (
            <section className="mt-20 border-t border-[#dedbd0] pb-20 pt-6" data-testid="section-empty-state">
              <div className="grid gap-8 sm:grid-cols-[1fr_1fr_1fr]">
                <div className="flex gap-3">
                  <span className="font-[var(--app-font-mono)] text-xs text-[#8a8d47]">01</span>
                  <div><p className="text-sm font-bold text-[#292b40]">Point to a project</p><p className="mt-1 text-xs leading-5 text-[#77786f]">Give the agent a public GitHub URL.</p></div>
                </div>
                <div className="flex gap-3">
                  <span className="font-[var(--app-font-mono)] text-xs text-[#8a8d47]">02</span>
                  <div><p className="text-sm font-bold text-[#292b40]">Read the evidence</p><p className="mt-1 text-xs leading-5 text-[#77786f]">Separate what is known from what is pending.</p></div>
                </div>
                <div className="flex gap-3">
                  <span className="font-[var(--app-font-mono)] text-xs text-[#8a8d47]">03</span>
                  <div><p className="text-sm font-bold text-[#292b40]">Choose your next move</p><p className="mt-1 text-xs leading-5 text-[#77786f]">Use the recommendations as your starting line.</p></div>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}