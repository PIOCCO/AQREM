import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHeader, LoadingState, ErrorState } from "../components/ui/States";
import { fetchProjectSummaries } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useProjectContext } from "../lib/projectContext";

type Summary = {
  id: string;
  name: string;
  description?: string;
  questionnaire_count: number;
  source_count: number;
  evidence_item_count: number;
  pending_review_count: number;
  potentially_stale_count: number;
};

const links = (projectId: string) => [
  { to: `/sources`, label: "Sources" },
  { to: `/evidence?project=${projectId}`, label: "Evidence" },
  { to: `/questionnaires`, label: "Questionnaires" },
  { to: `/review-queue`, label: "Review queue" },
  { to: `/answer-library`, label: "Answer library" },
  { to: `/stale-answers`, label: "Stale answers" },
  { to: `/audit`, label: "Activity" },
];

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const { session } = useAuth();
  const { setProjectId } = useProjectContext();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (projectId) setProjectId(projectId);
  }, [projectId, setProjectId]);

  useEffect(() => {
    if (!session || !projectId) return;
    fetchProjectSummaries(session)
      .then((rows: Summary[]) => {
        const match = rows.find((r) => r.id === projectId);
        if (!match) throw new Error("Project not found");
        setSummary(match);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load project"));
  }, [session?.organizationId, session?.token, projectId]);

  if (!projectId) return null;
  if (error) return <ErrorState message={error} />;
  if (!summary) return <LoadingState label="Loading project…" />;

  return (
    <div>
      <PageHeader title={summary.name} subtitle={summary.description ?? "Project workspace"} />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          ["Questionnaires", summary.questionnaire_count],
          ["Sources", summary.source_count],
          ["Evidence items", summary.evidence_item_count],
          ["Pending review", summary.pending_review_count],
        ].map(([label, value]) => (
          <div key={label as string} className="aq-metric">
            <div className="aq-metric-value">{value}</div>
            <div className="aq-metric-label">{label}</div>
          </div>
        ))}
      </div>
      {summary.potentially_stale_count > 0 && (
        <Link to="/stale-answers" className="aq-alert-warning block mb-6 hover:border-warning-border">
          {summary.potentially_stale_count} potentially stale answers — review now
        </Link>
      )}
      {summary.pending_review_count > 0 && (
        <div className="aq-alert-info mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <p>
            <span className="font-medium">{summary.pending_review_count}</span> answers awaiting review
          </p>
          <Link to="/review-queue" className="aq-btn-primary shrink-0">
            Open review queue
          </Link>
        </div>
      )}
      <nav className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {links(projectId).map((item) => (
          <Link key={item.to} to={item.to} className="aq-card aq-card-p aq-card-hover text-sm font-medium text-slate-800">
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
