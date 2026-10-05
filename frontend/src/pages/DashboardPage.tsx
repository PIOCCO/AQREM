import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchDashboardOverview } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

type Overview = {
  metrics: Record<string, number>;
  project_name?: string | null;
  recent_questionnaires: Array<{
    id: string;
    name: string;
    progress_percent: number;
    question_count: number;
    approved_count: number;
  }>;
};

const metricCards = [
  ["questions", "Questions", null],
  ["approved_answers", "Approved", null],
  ["pending_review", "Review", "/review-queue"],
  ["potentially_stale", "Stale", "/stale-answers"],
] as const;

export default function DashboardPage() {
  const { session, projectId, projectName } = useProjectContext();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      setOverview(await fetchDashboardOverview(session, projectId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load dashboard");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session?.organizationId, projectId]);

  const title = projectName ? projectName : "All projects";
  const pendingReview = overview?.metrics.pending_review ?? 0;

  return (
    <div>
      <PageHeader title="Dashboard" subtitle={`Operational overview · ${title}`} />
      {loading && <LoadingState label="Loading dashboard…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {overview && (
        <>
          <div className="flex flex-wrap gap-2 mb-6">
            <Link to="/projects" className="aq-btn-secondary">
              Create project
            </Link>
            <Link to="/sources" className="aq-btn-secondary">
              Add source
            </Link>
            <Link to="/questionnaires" className="aq-btn-secondary">
              Upload questionnaire
            </Link>
            <Link to="/review-queue" className="aq-btn-secondary">
              Review answers
            </Link>
            {(overview.metrics.potentially_stale ?? 0) > 0 && (
              <Link to="/stale-answers" className="aq-btn-secondary border-warning-border bg-warning-bg text-warning-text">
                Review stale ({overview.metrics.potentially_stale})
              </Link>
            )}
          </div>

          {pendingReview > 0 && (
            <div className="aq-alert-info mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <p>
                <span className="font-medium">{pendingReview}</span> answer{pendingReview === 1 ? "" : "s"} need
                review
              </p>
              <Link to="/review-queue" className="aq-btn-primary shrink-0">
                Review now
              </Link>
            </div>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {metricCards.map(([key, label, href]) => {
              const body = (
                <>
                  <div className="aq-metric-value">{overview.metrics[key] ?? 0}</div>
                  <div className="aq-metric-label">{label}</div>
                </>
              );
              if (href) {
                return (
                  <Link key={key} to={href} className="aq-metric block">
                    {body}
                  </Link>
                );
              }
              return (
                <div key={key} className="aq-metric">
                  {body}
                </div>
              );
            })}
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="aq-card aq-card-p">
              <h2 className="aq-section-title mb-4">Recent questionnaires</h2>
              {overview.recent_questionnaires.length === 0 ? (
                <p className="text-sm text-slate-600">
                  No questionnaires yet.{" "}
                  <Link to="/questionnaires" className="aq-link">
                    Create one
                  </Link>
                </p>
              ) : (
                <ul className="space-y-3">
                  {overview.recent_questionnaires.map((qn) => (
                    <li key={qn.id}>
                      <Link
                        to={`/questionnaires/${qn.id}`}
                        className="flex items-center justify-between gap-3 rounded-md px-2 py-2 -mx-2 hover:bg-surface-subtle transition-colors"
                      >
                        <span className="font-medium text-slate-900 truncate">{qn.name}</span>
                        <span className="text-sm text-slate-600 shrink-0">{qn.progress_percent}% complete</span>
                      </Link>
                      <div className="aq-progress-track mt-1">
                        <div className="aq-progress-fill" style={{ width: `${qn.progress_percent}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="aq-card aq-card-p">
              <h2 className="aq-section-title mb-4">Evidence & sources</h2>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-slate-500">Sources</dt>
                  <dd className="text-xl font-semibold tabular-nums">{overview.metrics.sources ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Evidence items</dt>
                  <dd className="text-xl font-semibold tabular-nums">{overview.metrics.evidence_items ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Indexing</dt>
                  <dd className="text-xl font-semibold tabular-nums">{overview.metrics.sources_indexing ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Insufficient evidence</dt>
                  <dd className="text-xl font-semibold tabular-nums">{overview.metrics.insufficient_evidence ?? 0}</dd>
                </div>
              </dl>
              <Link to="/sources" className="aq-link inline-block mt-4 text-sm">
                Manage sources
              </Link>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
