import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ConfidenceBadge, StatusBadge } from "../components/ui/Badges";
import { ErrorState, LoadingState } from "../components/ui/States";
import {
  approveAnswer,
  editAnswer,
  fetchQuestionDetail,
  loadSession,
  rejectAnswer,
} from "../lib/api";

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
    confidence: string;
    evidence_sufficiency: string;
    reasoning_summary?: string;
    status: string;
    generation_source?: string;
    library_entry_id?: string;
    evidence: EvidenceCitation[];
  };
};

export default function QuestionReviewPage() {
  const { questionId } = useParams();
  const session = loadSession();
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [editText, setEditText] = useState("");
  const [busy, setBusy] = useState(false);

  async function reload() {
    if (!session || !questionId) return;
    const data = await fetchQuestionDetail(session, questionId);
    setDetail(data);
    setEditText(data.answer?.draft_text ?? "");
  }

  useEffect(() => {
    reload().catch(() => setDetail(null));
  }, [questionId, session]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      await reload();
    } finally {
      setBusy(false);
    }
  }

  if (!session) return null;
  if (!detail) return <LoadingState label="Loading review workspace…" />;

  const answer = detail.answer;
  const evidenceBacked =
    answer && answer.evidence_sufficiency === "sufficient" && answer.evidence.length > 0;

  if (answer?.evidence_sufficiency === "insufficient") {
    return (
      <div className="max-w-3xl">
        <h1 className="text-xl font-semibold mb-2">{detail.question.external_id}</h1>
        <p className="text-slate-700 mb-4">{detail.question.text}</p>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-950">
          <h2 className="font-medium mb-2">Insufficient evidence</h2>
          <p className="text-sm">
            No reliable company evidence was found for this question. Review manually or add sources
            before approving.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="text-sm font-mono text-slate-500">{detail.question.external_id}</span>
        {answer && <StatusBadge status={answer.status} />}
        {answer && <ConfidenceBadge confidence={answer.confidence} />}
      </div>
      <h1 className="text-2xl font-semibold mb-6">{detail.question.text}</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-medium">AI answer</h2>
            </div>
            <p className="text-slate-800 leading-relaxed whitespace-pre-wrap">
              {answer?.draft_text ?? "No draft yet. Generate answers from the questionnaire page."}
            </p>
            {answer?.generation_source && (
              <p className="text-xs text-slate-500 mt-2 capitalize">
                Source: {answer.generation_source.replaceAll("_", " ")}
                {answer.library_entry_id ? ` · library ${answer.library_entry_id.slice(0, 8)}…` : ""}
              </p>
            )}
            {answer?.reasoning_summary && (
              <p className="text-sm text-slate-500 mt-3">{answer.reasoning_summary}</p>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="font-medium mb-3">Edit answer</h2>
            <textarea
              className="w-full min-h-28 rounded-lg border border-slate-300 p-3 text-sm"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
            />
            <button
              disabled={busy || !answer}
              onClick={() => answer && act(() => editAnswer(session, answer.id, editText))}
              className="mt-3 rounded-lg border border-slate-300 px-4 py-2 text-sm"
            >
              Save edit & approve
            </button>
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-medium">Evidence</h2>
              <span
                className={`text-xs px-2 py-1 rounded-full ${
                  evidenceBacked ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                }`}
              >
                {evidenceBacked ? "Evidence-backed" : "Insufficient evidence"}
              </span>
            </div>
            <div className="space-y-3">
              {(answer?.evidence ?? []).map((item) => (
                <div key={item.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                  <Link to={`/evidence/${item.id}`} className="font-medium text-blue-700 hover:underline">
                    {item.file_path}
                  </Link>
                  <div className="text-slate-500 text-xs mt-1">
                    {item.line_start != null
                      ? `Lines ${item.line_start}${item.line_end ? `–${item.line_end}` : ""}`
                      : "Document section"}
                    {item.repository ? ` · ${item.repository}` : ""}
                  </div>
                  <p className="mt-2 text-slate-700 line-clamp-4">{item.content_preview}</p>
                </div>
              ))}
              {!answer?.evidence?.length && (
                <p className="text-sm text-slate-500">No supporting evidence linked.</p>
              )}
            </div>
          </section>

          <div className="flex flex-col gap-2">
            <button
              disabled={busy || !answer}
              onClick={() => answer && act(() => approveAnswer(session, answer.id))}
              className="rounded-lg bg-slate-900 text-white py-2.5 text-sm font-medium disabled:opacity-50"
            >
              Approve
            </button>
            <button
              disabled={busy || !answer}
              onClick={() => answer && act(() => rejectAnswer(session, answer.id))}
              className="rounded-lg border border-red-200 text-red-700 py-2.5 text-sm disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
