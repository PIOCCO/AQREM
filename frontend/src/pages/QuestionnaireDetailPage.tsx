import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ConfidenceBadge, EvidenceStrengthBadge, StatusBadge } from "../components/ui/Badges";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import {
  downloadQuestionnaireExport,
  fetchQuestionnaire,
  fetchQuestionnaireQuestions,
  generateQuestionnaireAnswers,
} from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

type QuestionRow = {
  id: string;
  external_id: string;
  section?: string;
  text: string;
  answer?: {
    status?: string;
    confidence?: string;
    evidence_sufficiency?: string;
    potentially_stale?: boolean;
    evidence_strength?: string;
  };
};

export default function QuestionnaireDetailPage() {
  const { questionnaireId } = useParams();
  const { session } = useProjectContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const [meta, setMeta] = useState<{ name: string; status: string } | null>(null);
  const [questions, setQuestions] = useState<QuestionRow[]>([]);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const statusFilter = searchParams.get("status") ?? "";
  const search = searchParams.get("search") ?? "";

  async function load() {
    if (!session || !questionnaireId) return;
    setLoading(true);
    try {
      const [qn, qs] = await Promise.all([
        fetchQuestionnaire(session, questionnaireId),
        fetchQuestionnaireQuestions(session, questionnaireId, {
          status: statusFilter || undefined,
          search: search || undefined,
        }),
      ]);
      setMeta({ name: qn.name, status: qn.status });
      setQuestions(qs);
    } catch (e) {
      setMessage({ tone: "err", text: e instanceof Error ? e.message : "Failed to load questionnaire" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session, questionnaireId, statusFilter, search]);

  const approved = questions.filter((q) => q.answer?.status === "approved").length;
  const review = questions.filter((q) => q.answer?.status === "needs_review").length;
  const insufficient = questions.filter((q) => q.answer?.evidence_sufficiency === "insufficient").length;
  const progress = questions.length ? Math.round((approved / questions.length) * 100) : 0;

  async function onGenerateAll() {
    if (!session || !questionnaireId) return;
    setGenerating(true);
    setMessage(null);
    try {
      const result = await generateQuestionnaireAnswers(session, questionnaireId);
      setMessage({
        tone: "ok",
        text: `Generated ${result.generated} answers (${result.insufficient} with insufficient evidence).`,
      });
      await load();
    } catch (e) {
      setMessage({
        tone: "err",
        text: e instanceof Error ? e.message : "Unable to generate answers. Please try again.",
      });
    } finally {
      setGenerating(false);
    }
  }

  async function runExport(format: "csv" | "xlsx", approvedOnly: boolean) {
    if (!session || !questionnaireId) return;
    setExporting(true);
    setMessage(null);
    try {
      const { blob, filename } = await downloadQuestionnaireExport(session, questionnaireId, format, {
        approved_only: approvedOnly,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage({ tone: "ok", text: `Export completed (${filename}).` });
      setExportOpen(false);
    } catch (e) {
      setMessage({ tone: "err", text: e instanceof Error ? e.message : "Export failed." });
    } finally {
      setExporting(false);
    }
  }

  if (!session) return null;

  return (
    <div>
      <PageHeader
        title={meta?.name ?? "Questionnaire"}
        subtitle={`Progress ${progress}% · ${questions.length} questions · ${approved} approved · ${review} in review`}
        actions={
          <div className="flex flex-wrap gap-2 relative">
            <button
              type="button"
              disabled={generating}
              onClick={onGenerateAll}
              className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              {generating ? "Generating…" : "Generate answers"}
            </button>
            <Link
              to="/review-queue"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium"
            >
              Review queue
            </Link>
            <button
              type="button"
              onClick={() => setExportOpen((v) => !v)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium"
            >
              Export ▾
            </button>
            {exportOpen && (
              <div className="absolute right-0 top-full mt-1 z-10 w-52 rounded-lg border border-slate-200 bg-white shadow-lg py-1 text-sm">
                <button
                  type="button"
                  disabled={exporting}
                  className="block w-full text-left px-3 py-2 hover:bg-slate-50"
                  onClick={() => runExport("xlsx", false)}
                >
                  Export XLSX
                </button>
                <button
                  type="button"
                  disabled={exporting}
                  className="block w-full text-left px-3 py-2 hover:bg-slate-50"
                  onClick={() => runExport("csv", false)}
                >
                  Export CSV
                </button>
                <button
                  type="button"
                  disabled={exporting}
                  className="block w-full text-left px-3 py-2 hover:bg-slate-50"
                  onClick={() => runExport("xlsx", true)}
                >
                  Export approved (XLSX)
                </button>
              </div>
            )}
          </div>
        }
      />

      {message && (
        <p
          className={`mb-4 text-sm ${message.tone === "err" ? "text-red-700" : "text-emerald-800"}`}
          role="status"
        >
          {message.text}
        </p>
      )}

      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          placeholder="Search questions…"
          value={search}
          onChange={(e) => {
            const next = new URLSearchParams(searchParams);
            if (e.target.value) next.set("search", e.target.value);
            else next.delete("search");
            setSearchParams(next);
          }}
        />
        <select
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => {
            const next = new URLSearchParams(searchParams);
            if (e.target.value) next.set("status", e.target.value);
            else next.delete("status");
            setSearchParams(next);
          }}
        >
          <option value="">All statuses</option>
          <option value="approved">Approved</option>
          <option value="needs_review">Needs review</option>
          <option value="draft">Draft</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {loading && <LoadingState label="Loading questions…" />}
      {!loading && questions.length === 0 && (
        <EmptyState
          title="No questions yet"
          description="Upload a questionnaire file to extract questions, or adjust your filters."
        />
      )}

      <div className="space-y-3">
        {questions.map((q) => (
          <div key={q.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-xs font-mono text-slate-500">{q.external_id}</span>
              {q.section && <span className="text-xs text-slate-500">{q.section}</span>}
              {q.answer?.status && <StatusBadge status={q.answer.status} />}
              <ConfidenceBadge confidence={q.answer?.confidence} />
              <EvidenceStrengthBadge strength={q.answer?.evidence_strength} />
              {q.answer?.evidence_sufficiency === "insufficient" && (
                <span className="text-xs text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full">
                  Insufficient evidence
                </span>
              )}
            </div>
            <p className="font-medium mb-3">{q.text}</p>
            <Link
              to={`/questionnaires/${questionnaireId}/questions/${q.id}/review`}
              className="text-sm text-blue-600 hover:underline"
            >
              Open review workspace
            </Link>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-500 mt-4">{insufficient} questions flagged with insufficient evidence.</p>
    </div>
  );
}
