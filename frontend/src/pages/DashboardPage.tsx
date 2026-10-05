import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { IconFilter, IconGithub, IconSearch, IconShield } from "../components/icons/Icons";
import { QuestionnaireStatusBadge } from "../components/ui/Badges";
import { ErrorState, LoadingState } from "../components/ui/States";
import {
  fetchAnswerLibrary,
  fetchAuditLog,
  fetchDashboardOverview,
  fetchReviewQueue,
} from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useProjectContext } from "../lib/projectContext";

type Overview = {
  metrics: Record<string, number>;
  project_name?: string | null;
  recent_questionnaires: Array<{
    id: string;
    name: string;
    status: string;
    project_name?: string | null;
    progress_percent: number;
    question_count: number;
    approved_count: number;
  }>;
};

type ReviewItem = {
  question_id: string;
  questionnaire_id?: string;
  question_text: string;
  confidence: string;
};

type AuditItem = { action: string; resource_type: string; created_at: string };
type LibraryEntry = { id: string; question_text: string; status: string; evidence?: unknown[] };

function greetingName(fullName?: string, email?: string) {
  const first = fullName?.trim().split(/\s+/)[0];
  if (first) return first;
  return email?.split("@")[0] ?? "there";
}

function timeGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function progressBarClass(status: string) {
  const s = status.toLowerCase();
  if (s === "completed") return "bg-success";
  if (s === "in_review") return "bg-info";
  if (s === "draft") return "bg-amber-400";
  return "bg-slate-300";
}

function activityIcon(action: string, resource: string) {
  const a = `${action} ${resource}`.toLowerCase();
  if (a.includes("github") || a.includes("sync") || a.includes("source")) return <IconGithub className="h-5 w-5 text-slate-800" />;
  if (a.includes("export") || a.includes("document")) return <IconShield className="h-5 w-5 text-emerald-600" />;
  return <IconShield className="h-5 w-5 text-brand-violet" />;
}

function formatActivityTitle(action: string) {
  return action.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DashboardPage() {
  const { session, user } = useAuth();
  const { projectId } = useProjectContext();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [reviewItem, setReviewItem] = useState<ReviewItem | null>(null);
  const [activity, setActivity] = useState<AuditItem[]>([]);
  const [libraryPreview, setLibraryPreview] = useState<LibraryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tableSearch, setTableSearch] = useState("");

  async function load() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const [ov, queue, audit, library] = await Promise.all([
        fetchDashboardOverview(session, projectId),
        fetchReviewQueue(session, { project_id: projectId ?? undefined, limit: 1 }),
        fetchAuditLog(session, { limit: 5 }),
        fetchAnswerLibrary(session, { projectId, limit: 4 }),
      ]);
      setOverview(ov);
      setReviewItem(queue.items[0] ?? null);
      setActivity(audit.items.slice(0, 5));
      setLibraryPreview(library.slice(0, 4));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load dashboard");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session?.organizationId, session?.token, projectId]);

  const filteredQuestionnaires = useMemo(() => {
    const rows = overview?.recent_questionnaires ?? [];
    const q = tableSearch.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        (r.project_name ?? "").toLowerCase().includes(q),
    );
  }, [overview, tableSearch]);

  const metrics = [
    ["questions", "Questions"],
    ["approved_answers", "Approved Answers"],
    ["pending_review", "Pending Review"],
    ["insufficient_evidence", "Insufficient Evidence"],
    ["potentially_stale", "Potentially Stale"],
  ] as const;

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!overview) return null;

  const reviewHref =
    reviewItem?.questionnaire_id && reviewItem.question_id
      ? `/questionnaires/${reviewItem.questionnaire_id}/questions/${reviewItem.question_id}/review`
      : "/review-queue";

  return (
    <div className="max-w-[1400px] mx-auto space-y-8">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <h1 className="text-page-title text-slate-900">
            {timeGreeting()}, {greetingName(user?.fullName, user?.email)}
          </h1>
          <p className="mt-1 text-sm text-slate-600 max-w-xl">
            Manage company evidence and turn it into verified responses.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="relative w-44">
            <IconSearch className="absolute left-3 top-1/2 -h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="ref-header-search"
              placeholder="Search"
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
            />
          </div>
          <Link to="/questionnaires" className="aq-btn-secondary h-10">
            <IconFilter className="h-4 w-4" />
            Filter
          </Link>
        </div>
      </div>

      {(overview.metrics.sources_failed ?? 0) > 0 && (
        <div className="aq-alert-error flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p>
            <span className="font-medium">{overview.metrics.sources_failed}</span> source
            {overview.metrics.sources_failed === 1 ? "" : "s"} in error — check indexing and retry sync.
          </p>
          <Link to="/sources" className="aq-btn-secondary shrink-0">
            Open sources
          </Link>
        </div>
      )}
      {(overview.metrics.sources_indexing ?? 0) > 0 && (
        <div className="aq-alert-info mb-2">
          {overview.metrics.sources_indexing} source{overview.metrics.sources_indexing === 1 ? "" : "s"} currently
          indexing…
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {metrics.map(([key, label]) => {
          const value = overview.metrics[key] ?? 0;
          const href =
            key === "pending_review"
              ? "/review-queue"
              : key === "potentially_stale"
                ? "/stale-answers"
                : null;
          const inner = (
            <>
              <div className="ref-metric-value">{value}</div>
              <div className="ref-metric-label">{label}</div>
            </>
          );
          return href ? (
            <Link key={key} to={href} className="ref-metric-card block hover:border-border-strong transition-colors">
              {inner}
            </Link>
          ) : (
            <div key={key} className="ref-metric-card">
              {inner}
            </div>
          );
        })}
      </div>

      <div className="grid xl:grid-cols-3 gap-6">
        <section className="xl:col-span-2 aq-card shadow-card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <h2 className="text-section-title text-slate-900">Active Questionnaires</h2>
            <Link to="/questionnaires" className="text-sm text-brand-blue font-medium hover:underline">
              View all
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-surface-muted text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">Questionnaire Name</th>
                  <th className="px-5 py-3">Project</th>
                  <th className="px-5 py-3">Progress</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 w-32"></th>
                </tr>
              </thead>
              <tbody>
                {filteredQuestionnaires.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-slate-500">
                      No questionnaires yet.{" "}
                      <Link to="/questionnaires" className="text-brand-blue font-medium hover:underline">
                        Create one
                      </Link>
                    </td>
                  </tr>
                ) : (
                  filteredQuestionnaires.map((qn) => (
                    <tr key={qn.id} className="border-t border-border hover:bg-surface-muted/60">
                      <td className="px-5 py-4 font-medium text-slate-900">
                        <Link to={`/questionnaires/${qn.id}`} className="hover:text-brand-blue">
                          {qn.name}
                        </Link>
                      </td>
                      <td className="px-5 py-4 text-slate-600">{qn.project_name ?? "—"}</td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-700 tabular-nums w-10">{qn.progress_percent}%</span>
                          <div className="flex-1 max-w-[120px] h-2 rounded-full bg-surface-subtle overflow-hidden">
                            <div
                              className={`h-full rounded-full ${progressBarClass(qn.status)}`}
                              style={{ width: `${qn.progress_percent}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <QuestionnaireStatusBadge status={qn.status} />
                      </td>
                      <td className="px-5 py-4">
                        <div className="h-2 rounded-full bg-surface-subtle overflow-hidden">
                          <div
                            className={`h-full rounded-full opacity-80 ${progressBarClass(qn.status)}`}
                            style={{ width: `${Math.max(qn.progress_percent, 8)}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="aq-card shadow-card">
          <div className="px-5 py-4 border-b border-border">
            <h2 className="text-section-title text-slate-900">Evidence Activity</h2>
          </div>
          <ul className="divide-y divide-border">
            {activity.length === 0 ? (
              <li className="px-5 py-6 text-sm text-slate-500">No recent activity.</li>
            ) : (
              activity.map((item, idx) => (
                <li key={idx} className="px-5 py-4 flex gap-3">
                  <span className="mt-0.5">{activityIcon(item.action, item.resource_type)}</span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900">{formatActivityTitle(item.action)}</p>
                    <p className="text-xs text-slate-500 mt-0.5 capitalize">
                      {item.resource_type.replaceAll("_", " ")} · {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                </li>
              ))
            )}
          </ul>
          <div className="px-5 py-3 border-t border-border">
            <Link to="/audit" className="text-sm font-medium text-brand-blue hover:underline">
              View activity log
            </Link>
          </div>
        </section>
      </div>

      <div className="grid xl:grid-cols-2 gap-6">
        <section className="aq-card shadow-panel p-6">
          <h2 className="text-section-title text-slate-900 mb-4">Question Review workspace</h2>
          {reviewItem ? (
            <>
              <p className="text-label uppercase tracking-wide text-slate-500 mb-1">Question</p>
              <p className="text-sm font-medium text-slate-900 mb-4">{reviewItem.question_text}</p>
              <p className="text-label uppercase tracking-wide text-slate-500 mb-1">Confidence</p>
              <p className="text-sm font-medium text-success-text capitalize mb-4">{reviewItem.confidence || "—"}</p>
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border">
                {reviewItem.confidence && reviewItem.confidence !== "low" && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-success-bg text-success-text border border-success-border px-2.5 py-0.5 text-xs font-medium">
                    ✓ Evidence-backed
                  </span>
                )}
                <Link to={reviewHref} className="aq-btn-primary ml-auto">
                  Open review
                </Link>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-600">
              No answers waiting for review.{" "}
              <Link to="/review-queue" className="text-brand-blue font-medium hover:underline">
                Open review queue
              </Link>
            </p>
          )}
        </section>

        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-section-title text-slate-900">Answer Library preview</h2>
            <Link to="/answer-library" className="text-sm text-brand-blue font-medium hover:underline">
              View library
            </Link>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {libraryPreview.length === 0 ? (
              <p className="text-sm text-slate-500 sm:col-span-2 aq-card p-5">No library entries yet.</p>
            ) : (
              libraryPreview.map((entry) => (
                <Link
                  key={entry.id}
                  to={`/answer-library/${entry.id}`}
                  className="aq-card p-4 hover:border-border-strong transition-colors shadow-card"
                >
                  <div className="flex gap-3">
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-control bg-success-bg text-success">
                      <IconShield className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900 truncate">{entry.question_text.slice(0, 40)}</p>
                      <p className="text-xs text-slate-500 mt-1 capitalize">
                        {entry.status.replaceAll("_", " ")}
                        {Array.isArray(entry.evidence) ? ` · ${entry.evidence.length} sources` : ""}
                      </p>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
