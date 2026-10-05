import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ConfidenceBadge, StatusBadge } from "../components/ui/Badges";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchReviewQueue } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

type Item = {
  answer_id: string;
  question_id: string;
  question_external_id: string;
  question_text: string;
  questionnaire_id?: string;
  questionnaire_name?: string;
  reason: string;
  potentially_stale: boolean;
  confidence: string;
  status: string;
};

export default function ReviewQueuePage() {
  const { session, projectId } = useProjectContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const search = searchParams.get("search") ?? "";

  async function load() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReviewQueue(session, {
        project_id: projectId ?? undefined,
        search: search || undefined,
        limit: 100,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session?.organizationId, projectId, search]);

  const staleCount = items.filter((i) => i.potentially_stale).length;

  return (
    <div>
      <PageHeader
        title="Review queue"
        subtitle={`${total} answers waiting for human review`}
        actions={
          staleCount > 0 ? (
            <Link
              to="/stale-answers"
              className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            >
              {staleCount} evidence changes
            </Link>
          ) : undefined
        }
      />
      <input
        className="mb-4 w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 text-sm"
        placeholder="Search questions…"
        value={search}
        onChange={(e) => {
          const next = new URLSearchParams(searchParams);
          if (e.target.value) next.set("search", e.target.value);
          else next.delete("search");
          setSearchParams(next);
        }}
      />
      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState
          title="Review queue is empty"
          description="When AI-generated answers need approval, they will appear here."
        />
      )}
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.answer_id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-xs font-mono text-slate-500">{item.question_external_id}</span>
              <StatusBadge status={item.status} />
              <ConfidenceBadge confidence={item.confidence} />
              <span className="text-xs rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">
                {item.reason}
              </span>
            </div>
            <p className="font-medium text-slate-900 mb-1">{item.question_text}</p>
            {item.questionnaire_name && (
              <p className="text-xs text-slate-500 mb-3">{item.questionnaire_name}</p>
            )}
            {item.potentially_stale ? (
              <Link
                to={`/stale-answers/${item.answer_id}`}
                className="text-sm text-amber-800 hover:underline"
              >
                Review evidence change
              </Link>
            ) : (
              item.questionnaire_id && (
                <Link
                  to={`/questionnaires/${item.questionnaire_id}/questions/${item.question_id}/review`}
                  className="text-sm text-blue-600 hover:underline"
                >
                  Open review workspace
                </Link>
              )
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
