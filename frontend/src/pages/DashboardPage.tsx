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

  return (
    <div>
      <PageHeader title="Dashboard" subtitle={`Operational overview · ${title}`} />
      {loading && <LoadingState label="Loading dashboard…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {overview && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {metricCards.map(([key, label, href]) => {
              const body = (
                <>
                  <div className="text-2xl font-semibold">{overview.metrics[key] ?? 0}</div>
                  <div className="text-sm text-slate-500">{label}</div>
                </>
              );
              if (href) {
                return (
                  <Link
                    key={key}
                    to={href}
                    className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300"
                  >
                    {body}
                  </Link>
                );
              }
              return (
                <div key={key} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  {body}
                </div>
              );
            })}
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium mb-4">Recent questionnaires</h2>
              {overview.recent_questionnaires.length === 0 ? (
                <p className="text-sm text-slate-600">
                  No questionnaires yet.{" "}
                  <Link to="/questionnaires" className="text-blue-600 hover:underline">
                    Create one
                  </Link>
                </p>
              ) : (
                <ul className="space-y-3">
                  {overview.recent_questionnaires.map((qn) => (
                    <li key={qn.id}>
                      <Link
                        to={`/questionnaires/${qn.id}`}
                        className="flex items-center justify-between gap-3 hover:bg-slate-50 rounded-lg px-2 py-2 -mx-2"
                      >
                        <span className="font-medium text-slate-900">{qn.name}</span>
                        <span className="text-sm text-slate-600">{qn.progress_percent}% complete</span>
                      </Link>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1">
                        <div
                          className="h-full bg-emerald-500"
                          style={{ width: `${qn.progress_percent}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium mb-4">Evidence & sources</h2>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-slate-500">Sources</dt>
                  <dd className="text-xl font-semibold">{overview.metrics.sources ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Evidence items</dt>
                  <dd className="text-xl font-semibold">{overview.metrics.evidence_items ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Indexing</dt>
                  <dd className="text-xl font-semibold">{overview.metrics.sources_indexing ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Insufficient evidence</dt>
                  <dd className="text-xl font-semibold">{overview.metrics.insufficient_evidence ?? 0}</dd>
                </div>
              </dl>
              <Link to="/sources" className="inline-block mt-4 text-sm text-blue-600 hover:underline">
                Manage sources
              </Link>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
