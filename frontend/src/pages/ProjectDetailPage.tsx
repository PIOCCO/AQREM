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
  }, [session, projectId]);

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
          <div key={label as string} className="rounded-xl border bg-white p-4">
            <div className="text-2xl font-semibold">{value}</div>
            <div className="text-sm text-slate-500">{label}</div>
          </div>
        ))}
      </div>
      {summary.potentially_stale_count > 0 && (
        <Link
          to="/stale-answers"
          className="block mb-6 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          {summary.potentially_stale_count} potentially stale answers — review now
        </Link>
      )}
      <nav className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {links(projectId).map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium hover:border-slate-400"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
