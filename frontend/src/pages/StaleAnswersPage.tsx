import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StatusBadge } from "../components/ui/Badges";
import { EmptyState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchStaleAnswers } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useProjectContext } from "../lib/projectContext";

type StaleItem = {
  answer_id: string;
  question_text: string;
  project_name?: string;
  status: string;
  stale_detected_at?: string;
  changed_evidence_count: number;
};

export default function StaleAnswersPage() {
  const { session } = useAuth();
  const { projectId } = useProjectContext();
  const [items, setItems] = useState<StaleItem[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    setLoading(true);
    fetchStaleAnswers(session, {
      search: debouncedSearch || undefined,
      project_id: projectId ?? undefined,
    })
      .then((data) => {
        if (!cancelled) {
          setItems(data.items);
          setTotal(data.total);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session?.organizationId, session?.token, debouncedSearch, projectId]);

  if (!session) return <p className="text-sm text-slate-600">Please sign in.</p>;

  return (
    <div>
      <PageHeader title="Potentially stale answers" subtitle={`${total} answers may need re-review after evidence changes`} />
      <input
        className="aq-input mb-6 max-w-md"
        placeholder="Search questions…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {loading && <LoadingState label="Loading stale answers…" />}
      {!loading && items.length === 0 && (
        <EmptyState
          title="No stale answers"
          description="When approved answers are linked to evidence that later changes, they will appear here for review."
        />
      )}
      <div className="space-y-3">
        {items.map((item) => (
          <article key={item.answer_id} className="aq-card aq-card-p border-warning-border">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <StatusBadge status={item.status || "potentially_stale"} />
            </div>
            <p className="font-medium text-slate-900 line-clamp-2">{item.question_text}</p>
            <p className="text-sm text-slate-500 mt-1">
              Project: {item.project_name ?? "—"} · Evidence changes: {item.changed_evidence_count}
            </p>
            <Link to={`/stale-answers/${item.answer_id}`} className="aq-link inline-block mt-3 text-sm">
              Review
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
