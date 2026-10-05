import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../components/ui/States";
import {
  approveAnswer,
  fetchStaleAnswerDetail,
  loadSession,
  regenerateStaleAnswer,
  rejectAnswer,
  revalidateStaleAnswer,
} from "../lib/api";

export default function StaleAnswerDetailPage() {
  const { answerId } = useParams();
  const session = loadSession();
  const [detail, setDetail] = useState<any>(null);
  const [revalidateResult, setRevalidateResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    if (!session || !answerId) return;
    setDetail(await fetchStaleAnswerDetail(session, answerId));
  }

  useEffect(() => {
    reload().catch(() => setError("Unable to load stale answer."));
  }, [answerId, session]);

  if (!session) return <p className="text-sm text-slate-600">Please sign in.</p>;
  if (error && !detail) return <ErrorState message={error} onRetry={reload} />;
  if (!detail) return <LoadingState label="Loading staleness review…" />;

  return (
    <div className="max-w-5xl space-y-6">
      <Link to="/stale-answers" className="aq-link text-sm">
        ← Back to stale queue
      </Link>
      <div className="aq-alert-warning">
        <h1 className="font-semibold text-warning-text">Evidence changed</h1>
        <p className="text-sm mt-1">
          This approved answer may no longer be valid because supporting evidence changed after approval.
        </p>
      </div>

      <section className="aq-workspace-section">
        <p className="aq-panel-label">Question</p>
        <h2 className="text-page-title text-slate-900 leading-snug mb-2">{detail.question_text}</h2>
        <p className="text-sm text-slate-500">
          Project: {detail.project_name ?? "—"} · Questionnaire: {detail.questionnaire_name}
        </p>
        {detail.approved_text && (
          <div className="mt-4 pt-4 border-t border-border">
            <h3 className="aq-panel-label">Last approved answer</h3>
            <p className="text-sm whitespace-pre-wrap text-slate-800">{detail.approved_text}</p>
          </div>
        )}
        <div className="mt-4 pt-4 border-t border-border">
          <h3 className="aq-panel-label">Current draft</h3>
          <p className="text-sm whitespace-pre-wrap text-slate-800">{detail.draft_text}</p>
        </div>
      </section>

      <section className="aq-workspace-section space-y-4">
        <h2 className="aq-section-title">Changed evidence</h2>
        {detail.changed_evidence.map((ev: any) => (
          <div key={ev.event_id} className="aq-evidence-citation">
            <div className="font-medium font-mono text-sm break-all">{ev.file_path}</div>
            <div className="text-xs text-slate-500 mt-1 font-mono">
              Previous commit: {ev.previous_commit_hash ?? "—"} · Current commit: {ev.current_commit_hash ?? "—"}
            </div>
            <div className="text-xs text-slate-500 mt-1 font-mono">
              Previous hash: {ev.snapshot_content_hash.slice(0, 12)}… · Current hash:{" "}
              {ev.current_content_hash.slice(0, 12)}…
            </div>
            {ev.previous_content_excerpt && (
              <div className="mt-3">
                <div className="text-label uppercase tracking-wide text-slate-500 mb-1">Previous excerpt</div>
                <pre className="aq-code-block text-xs mt-1">{ev.previous_content_excerpt}</pre>
              </div>
            )}
            {ev.current_content_excerpt && (
              <div className="mt-3">
                <div className="text-label uppercase tracking-wide text-slate-500 mb-1">Current excerpt</div>
                <pre className="aq-code-block text-xs mt-1">{ev.current_content_excerpt}</pre>
              </div>
            )}
          </div>
        ))}
      </section>

      {revalidateResult && (
        <div className={revalidateResult.current ? "aq-alert-success" : "aq-alert-warning"}>
          {revalidateResult.current ? (
            <p>Evidence is still valid. Stale state cleared.</p>
          ) : (
            <p>Evidence changed. Review and regenerate if needed.</p>
          )}
        </div>
      )}
      {message && <div className="aq-alert-info">{message}</div>}

      <div className="flex flex-wrap gap-2">
        <button
          disabled={busy}
          className="aq-btn-secondary"
          onClick={async () => {
            if (!session || !answerId) return;
            setBusy(true);
            try {
              setRevalidateResult(await revalidateStaleAnswer(session, answerId));
              await reload();
            } finally {
              setBusy(false);
            }
          }}
        >
          Revalidate
        </button>
        <button
          disabled={busy}
          className="aq-btn-primary"
          onClick={async () => {
            if (!session || !answerId) return;
            setBusy(true);
            try {
              await regenerateStaleAnswer(session, answerId);
              setMessage("Answer regenerated from current evidence.");
              await reload();
            } finally {
              setBusy(false);
            }
          }}
        >
          Regenerate answer
        </button>
        <button
          disabled={busy}
          className="aq-btn-success"
          onClick={async () => {
            if (!session || !answerId) return;
            setBusy(true);
            try {
              await approveAnswer(session, answerId);
              setMessage("Answer approved and marked current.");
              await reload();
            } finally {
              setBusy(false);
            }
          }}
        >
          Approve
        </button>
        <button
          disabled={busy}
          className="aq-btn-danger"
          onClick={async () => {
            if (!session || !answerId) return;
            setBusy(true);
            try {
              await rejectAnswer(session, answerId);
              setMessage("Regenerated draft rejected; previous approved answer preserved when available.");
              await reload();
            } finally {
              setBusy(false);
            }
          }}
        >
          Reject
        </button>
      </div>
    </div>
  );
}
