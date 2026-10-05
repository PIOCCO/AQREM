import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useToast } from "../components/ui/Toast";
import { ConfidenceBadge, EvidenceStrengthBadge, StatusBadge } from "../components/ui/Badges";
import { ErrorState, LoadingState } from "../components/ui/States";
import {
  approveAnswer,
  editAnswer,
  fetchQuestionDetail,
  regenerateQuestionAnswer,
  rejectAnswer,
} from "../lib/api";
import { useAuth } from "../lib/authContext";
import { canEditContent, canReviewAnswers } from "../lib/roles";

type EvidenceCitation = {
  id: string;
  file_path: string;
  line_start?: number;
  line_end?: number;
  repository?: string;
  evidence_strength?: string;
  content_preview: string;
};

type QuestionDetail = {
  question: { external_id: string; section?: string; text: string };
  answer?: {
    id: string;
    draft_text: string;
    approved_text?: string;
    confidence: string;
    evidence_sufficiency: string;
    reasoning_summary?: string;
    status: string;
    generation_source?: string;
    library_entry_id?: string;
    potentially_stale?: boolean;
    evidence: EvidenceCitation[];
  };
};

export default function QuestionReviewPage() {
  const { questionId } = useParams();
  const { session, user } = useAuth();
  const toast = useToast();
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [editText, setEditText] = useState("");
  const [busy, setBusy] = useState(false);
  const [genPhase, setGenPhase] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canEdit = user ? canEditContent(user.role) : false;
  const canReview = user ? canReviewAnswers(user.role) : false;

  async function reload() {
    if (!session || !questionId) return;
    const data = await fetchQuestionDetail(session, questionId);
    setDetail(data);
    setEditText(data.answer?.draft_text ?? "");
  }

  useEffect(() => {
    reload().catch(() => setError("Unable to load question."));
  }, [questionId, session]);

  async function act(fn: () => Promise<unknown>, successMsg?: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      if (successMsg) toast.push(successMsg);
      await reload();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Action failed";
      setError(msg);
      toast.push(msg, "err");
    } finally {
      setBusy(false);
      setGenPhase(null);
    }
  }

  async function onGenerate() {
    if (!session || !questionId || !canEdit) return;
    setGenPhase("Finding relevant evidence…");
    await new Promise((r) => setTimeout(r, 400));
    setGenPhase("Generating answer…");
    await act(() => regenerateQuestionAnswer(session, questionId), "Answer generated.");
  }

  if (!session) return null;
  if (!detail && !error) return <LoadingState label="Loading review workspace…" />;
  if (error && !detail) return <ErrorState message={error} onRetry={() => reload()} />;

  const answer = detail?.answer;
  const insufficient = answer?.evidence_sufficiency === "insufficient";

  return (
    <div className="max-w-6xl">
      {genPhase && (
        <p className="mb-4 text-sm text-slate-600" role="status">
          {genPhase}
        </p>
      )}
      {error && <p className="mb-4 text-sm text-red-700">{error}</p>}

      {answer?.potentially_stale && (
        <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm">
          Potentially stale — evidence may have changed.{" "}
          <Link to={`/stale-answers/${answer.id}`} className="text-amber-900 underline font-medium">
            Open staleness review
          </Link>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-sm font-mono text-slate-500">{detail?.question.external_id}</span>
        {answer && <StatusBadge status={answer.status} />}
        {answer && <ConfidenceBadge confidence={answer.confidence} />}
      </div>
      <h1 className="text-2xl font-semibold mb-6">{detail?.question.text}</h1>

      {!answer && canEdit && (
        <button
          type="button"
          disabled={busy}
          onClick={onGenerate}
          className="mb-6 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm disabled:opacity-50"
        >
          Generate answer
        </button>
      )}

      {insufficient && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-950 mb-6">
          <h2 className="font-medium mb-2">Insufficient evidence</h2>
          <p className="text-sm">
            The system could not find enough company evidence to produce a reliable answer. Connect sources,
            run indexing, then regenerate.
          </p>
          {canEdit && (
            <button
              type="button"
              disabled={busy}
              onClick={onGenerate}
              className="mt-3 rounded-lg border border-amber-400 px-3 py-1.5 text-sm"
            >
              Retry generation
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium mb-3">AI answer</h2>
            <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">
              {answer?.draft_text ?? "No draft yet."}
            </p>
            {answer?.approved_text && answer.approved_text !== answer.draft_text && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <h3 className="text-xs font-medium text-slate-500 mb-1">Last approved</h3>
                <p className="text-sm whitespace-pre-wrap">{answer.approved_text}</p>
              </div>
            )}
            {answer?.generation_source && (
              <p className="text-xs text-slate-500 mt-3 capitalize">
                Generation: {answer.generation_source.replaceAll("_", " ")}
                {answer.library_entry_id && (
                  <>
                    {" "}
                    ·{" "}
                    <Link to={`/answer-library/${answer.library_entry_id}`} className="text-blue-600 hover:underline">
                      library entry
                    </Link>
                  </>
                )}
              </p>
            )}
            {answer?.reasoning_summary && (
              <p className="text-sm text-slate-500 mt-2">{answer.reasoning_summary}</p>
            )}
          </section>

          {canReview && answer && (
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-medium mb-3">Edit answer</h2>
              <textarea
                className="w-full min-h-28 rounded-lg border border-slate-300 p-3 text-sm"
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
              />
              <button
                disabled={busy}
                onClick={() => act(() => editAnswer(session, answer.id, editText), "Answer saved and approved.")}
                className="mt-3 rounded-lg border border-slate-300 px-4 py-2 text-sm"
              >
                Save edit & approve
              </button>
            </section>
          )}
        </div>

        <div className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium mb-3">Evidence citations</h2>
            <div className="space-y-3">
              {(answer?.evidence ?? []).map((item, idx) => (
                <div key={item.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                  <span className="text-xs text-slate-500 mr-2">[{idx + 1}]</span>
                  <Link to={`/evidence/${item.id}`} className="font-medium text-blue-700 hover:underline">
                    {item.file_path}
                  </Link>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {item.line_start != null && (
                      <span className="text-xs text-slate-500">
                        lines {item.line_start}
                        {item.line_end ? `–${item.line_end}` : ""}
                      </span>
                    )}
                    {item.repository && <span className="text-xs text-slate-500">{item.repository}</span>}
                    <EvidenceStrengthBadge strength={item.evidence_strength} />
                  </div>
                  <p className="mt-2 text-slate-700 line-clamp-4 whitespace-pre-wrap">{item.content_preview}</p>
                </div>
              ))}
              {!answer?.evidence?.length && (
                <p className="text-sm text-slate-500">No supporting evidence linked.</p>
              )}
            </div>
          </section>

          <div className="flex flex-col gap-2">
            {canEdit && answer && (
              <button
                disabled={busy}
                onClick={onGenerate}
                className="rounded-lg border border-slate-300 py-2.5 text-sm disabled:opacity-50"
              >
                Regenerate answer
              </button>
            )}
            {canReview && answer && (
              <>
                <button
                  disabled={busy || insufficient}
                  onClick={() => act(() => approveAnswer(session, answer.id), "Answer approved.")}
                  className="rounded-lg bg-slate-900 text-white py-2.5 text-sm font-medium disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  disabled={busy}
                  onClick={() => act(() => rejectAnswer(session, answer.id), "Answer rejected.")}
                  className="rounded-lg border border-red-200 text-red-700 py-2.5 text-sm disabled:opacity-50"
                >
                  Reject
                </button>
              </>
            )}
            {!canReview && !canEdit && (
              <p className="text-sm text-slate-500">You have read-only access to this workspace.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
