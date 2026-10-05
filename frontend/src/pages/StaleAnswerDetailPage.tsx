import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
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

  async function reload() {
    if (!session || !answerId) return;
    setDetail(await fetchStaleAnswerDetail(session, answerId));
  }

  useEffect(() => {
    reload().catch(() => setDetail(null));
  }, [answerId, session]);

  if (!session) return <p>Please sign in.</p>;
  if (!detail) return <p>Loading…</p>;

  return (
    <div className="max-w-5xl space-y-6">
      <Link to="/stale-answers" className="text-sm text-blue-600 hover:underline">
        ← Back to stale queue
      </Link>
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
        <h1 className="font-semibold text-amber-900">Evidence changed</h1>
        <p className="text-sm text-amber-800 mt-1">
          This approved answer may no longer be valid because supporting evidence changed after approval.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-medium mb-2">{detail.question_text}</h2>
        <p className="text-sm text-slate-500">
          Project: {detail.project_name ?? "—"} · Questionnaire: {detail.questionnaire_name}
        </p>
        {detail.approved_text && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-slate-700">Last approved answer</h3>
            <p className="text-sm mt-1 whitespace-pre-wrap">{detail.approved_text}</p>
          </div>
        )}
        <div className="mt-4">
          <h3 className="text-sm font-medium text-slate-700">Current draft</h3>
          <p className="text-sm mt-1 whitespace-pre-wrap">{detail.draft_text}</p>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <h2 className="font-medium">Changed evidence</h2>
        {detail.changed_evidence.map((ev: any) => (
          <div key={ev.event_id} className="rounded-lg bg-slate-50 p-4 text-sm">
            <div className="font-medium">{ev.file_path}</div>
            <div className="text-xs text-slate-500 mt-1">
              Previous commit: {ev.previous_commit_hash ?? "—"} · Current commit:{" "}
              {ev.current_commit_hash ?? "—"}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              Previous hash: {ev.snapshot_content_hash.slice(0, 12)}… · Current hash:{" "}
              {ev.current_content_hash.slice(0, 12)}…
            </div>
            {ev.previous_content_excerpt && (
              <div className="mt-3">
                <div className="text-xs font-medium text-slate-600">Previous excerpt</div>
                <pre className="text-xs whitespace-pre-wrap mt-1">{ev.previous_content_excerpt}</pre>
              </div>
            )}
            {ev.current_content_excerpt && (
              <div className="mt-3">
                <div className="text-xs font-medium text-slate-600">Current excerpt</div>
                <pre className="text-xs whitespace-pre-wrap mt-1">{ev.current_content_excerpt}</pre>
              </div>
            )}
          </div>
        ))}
      </section>

      {revalidateResult && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
          {revalidateResult.current ? (
            <p className="text-green-700">Evidence is still valid. Stale state cleared.</p>
          ) : (
            <p className="text-amber-700">Evidence changed. Review and regenerate if needed.</p>
          )}
        </div>
      )}
      {message && <p className="text-sm text-slate-600">{message}</p>}

      <div className="flex flex-wrap gap-2">
        <button
          disabled={busy}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
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
          className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm"
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
          className="rounded-lg bg-green-700 text-white px-4 py-2 text-sm"
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
          className="rounded-lg border border-red-200 text-red-700 px-4 py-2 text-sm"
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
