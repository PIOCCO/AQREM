import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useToast } from "../components/ui/Toast";
import { IconCopy } from "../components/icons/Icons";
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
  }, [questionId, session?.organizationId, session?.token]);

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
        <p className="mb-4 text-sm text-slate-600 flex items-center gap-2" role="status">
          <span className="aq-spinner" aria-hidden />
          {genPhase}
        </p>
      )}
      {error && <div className="aq-alert-error mb-4">{error}</div>}

      {answer?.potentially_stale && (
        <div className="aq-alert-warning mb-4">
          Potentially stale — evidence may have changed.{" "}
          <Link to={`/stale-answers/${answer.id}`} className="aq-link text-warning-text">
            Open staleness review
          </Link>
        </div>
      )}

      <section className="aq-workspace-section mb-6">
        <p className="aq-panel-label">Question</p>
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-sm font-mono text-slate-500">{detail?.question.external_id}</span>
          {detail?.question.section && (
            <span className="text-xs text-slate-500">{detail.question.section}</span>
          )}
          {answer && <StatusBadge status={answer.status} />}
        </div>
        <h1 className="text-page-title text-slate-900 leading-snug">{detail?.question.text}</h1>
        {!answer && canEdit && (
          <button type="button" disabled={busy} onClick={onGenerate} className="aq-btn-primary mt-4">
            Generate answer
          </button>
        )}
      </section>

      {insufficient && (
        <div className="aq-alert-warning mb-6">
          <p className="font-medium mb-2">Insufficient evidence</p>
          <p className="text-sm mb-3">
            The system could not find enough company evidence to produce a reliable answer. Connect sources,
            run indexing, then regenerate.
          </p>
          {canEdit && (
            <button type="button" disabled={busy} onClick={onGenerate} className="aq-btn-secondary">
              Retry generation
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <section className="aq-workspace-section shadow-panel">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h2 className="aq-section-title">AI answer</h2>
              {answer && <ConfidenceBadge confidence={answer.confidence} />}
            </div>
            <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">
              {answer?.draft_text ?? "No draft yet."}
            </p>
            {answer?.approved_text && answer.approved_text !== answer.draft_text && (
              <div className="mt-4 pt-4 border-t border-border">
                <h3 className="aq-panel-label mb-1">Last approved</h3>
                <p className="text-sm whitespace-pre-wrap text-slate-700">{answer.approved_text}</p>
              </div>
            )}
            {answer?.generation_source && (
              <p className="text-xs text-slate-500 mt-3 capitalize">
                Generation: {answer.generation_source.replaceAll("_", " ")}
                {answer.library_entry_id && (
                  <>
                    {" "}
                    ·{" "}
                    <Link to={`/answer-library/${answer.library_entry_id}`} className="aq-link text-xs">
                      library entry
                    </Link>
                  </>
                )}
              </p>
            )}
            {answer?.reasoning_summary && (
              <p className="text-sm text-slate-600 mt-2 border-l-2 border-border pl-3">{answer.reasoning_summary}</p>
            )}
          </section>

          {canReview && answer && (
            <section id="aq-edit-answer" className="aq-workspace-section shadow-panel">
              <h2 className="aq-section-title mb-3">Edit answer</h2>
              <textarea className="aq-textarea" value={editText} onChange={(e) => setEditText(e.target.value)} />
              <button
                disabled={busy}
                onClick={() => act(() => editAnswer(session, answer.id, editText), "Answer saved and approved.")}
                className="aq-btn-secondary mt-3"
              >
                Save edit & approve
              </button>
            </section>
          )}

          <div className="flex flex-col gap-2">
            {canEdit && answer && (
              <button disabled={busy} onClick={onGenerate} className="aq-btn-secondary disabled:opacity-50">
                Regenerate answer
              </button>
            )}
            {canReview && answer && (
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border">
                <span className="inline-flex items-center gap-1 rounded-full bg-success-bg text-success-text border border-success-border px-2.5 py-0.5 text-xs font-medium">
                  ✓ Evidence-backed
                </span>
                <button
                  disabled={busy || insufficient}
                  onClick={() => act(() => approveAnswer(session, answer.id), "Answer approved.")}
                  className="aq-btn-primary disabled:opacity-50 ml-auto"
                >
                  Approve
                </button>
                {canEdit && (
                  <button
                    type="button"
                    className="aq-btn-secondary"
                    onClick={() => document.getElementById("aq-edit-answer")?.scrollIntoView({ behavior: "smooth" })}
                  >
                    Edit
                  </button>
                )}
                <button
                  disabled={busy}
                  onClick={() => act(() => rejectAnswer(session, answer.id), "Answer rejected.")}
                  className="aq-btn-danger disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            )}
            {!canReview && !canEdit && (
              <p className="text-sm text-slate-500">You have read-only access to this workspace.</p>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <section className="aq-workspace-section shadow-panel lg:min-h-[20rem]">
            <h2 className="aq-panel-label">Evidence</h2>
            <div className="space-y-3">
              {(answer?.evidence ?? []).map((item, idx) => (
                <div key={item.id} className="aq-evidence-citation">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <span className="text-xs font-medium text-slate-500 mr-2">[{idx + 1}]</span>
                      <Link to={`/evidence/${item.id}`} className="aq-link font-medium break-all font-mono text-xs">
                        {item.file_path}
                      </Link>
                    </div>
                    <button
                      type="button"
                      className="shrink-0 p-1.5 rounded-control text-slate-500 hover:bg-surface hover:text-slate-800"
                      aria-label="Copy file path"
                      onClick={() => navigator.clipboard.writeText(item.file_path)}
                    >
                      <IconCopy />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {item.line_start != null && (
                      <span className="text-xs text-slate-500 font-mono">
                        lines {item.line_start}
                        {item.line_end ? `–${item.line_end}` : ""}
                      </span>
                    )}
                    {item.repository && <span className="text-xs text-slate-500">{item.repository}</span>}
                    <EvidenceStrengthBadge strength={item.evidence_strength} />
                  </div>
                  <pre className="mt-2 text-slate-700 line-clamp-4 whitespace-pre-wrap font-mono text-xs leading-relaxed">
                    {item.content_preview}
                  </pre>
                  <Link to={`/evidence/${item.id}`} className="aq-btn-ghost mt-2 px-0 text-xs">
                    View evidence →
                  </Link>
                </div>
              ))}
              {!answer?.evidence?.length && (
                <p className="text-sm text-slate-500">No supporting evidence linked.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
