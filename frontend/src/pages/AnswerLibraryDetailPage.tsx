import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { StatusBadge } from "../components/ui/Badges";
import { ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchAnswerLibraryEntry, validateLibraryEntry } from "../lib/api";
import { useAuth } from "../lib/authContext";

export default function AnswerLibraryDetailPage() {
  const { entryId } = useParams();
  const { session } = useAuth();
  const [entry, setEntry] = useState<any>(null);
  const [validation, setValidation] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !entryId) return;
    Promise.all([fetchAnswerLibraryEntry(session, entryId), validateLibraryEntry(session, entryId)])
      .then(([e, v]) => {
        setEntry(e);
        setValidation(v);
      })
      .catch(() => setError("Unable to load library entry."));
  }, [session?.organizationId, session?.token, entryId]);

  if (!session) return <p className="text-sm text-slate-600">Please sign in.</p>;
  if (error) return <ErrorState message={error} />;
  if (!entry) return <LoadingState label="Loading entry…" />;

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader title="Answer details" subtitle="Library entry with evidence snapshots." />
      <section className="aq-workspace-section">
        <h2 className="aq-panel-label">Question</h2>
        <p className="text-slate-900">{entry.question_text}</p>
      </section>
      <section className="aq-workspace-section">
        <h2 className="aq-panel-label">Approved answer</h2>
        <p className="whitespace-pre-wrap text-slate-800 leading-relaxed">{entry.answer_text}</p>
      </section>
      <section className="aq-workspace-section">
        <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
          <h2 className="aq-section-title">Evidence validation</h2>
          <StatusBadge status={validation?.valid ? "approved" : "needs_review"} />
        </div>
        <p className="text-sm text-slate-600 mb-3">
          {validation?.valid ? "Snapshot hashes match current indexed evidence." : "One or more snapshots may be outdated."}
        </p>
        <ul className="space-y-2 text-sm">
          {(entry.evidence ?? []).map((ev: any, idx: number) => (
            <li key={idx} className="aq-evidence-citation">
              <div className="font-medium font-mono text-sm break-all">{ev.file_path}</div>
              <div className="text-xs text-slate-500 font-mono mt-1">hash {ev.snapshot_content_hash.slice(0, 12)}…</div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
