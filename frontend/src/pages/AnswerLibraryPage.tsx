import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StatusBadge } from "../components/ui/Badges";
import { EmptyState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchAnswerLibrary, loadSession } from "../lib/api";

type Entry = {
  id: string;
  question_text: string;
  answer_text: string;
  status: string;
  reuse_count: number;
  project_id?: string;
};

export default function AnswerLibraryPage() {
  const session = loadSession();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session) return;
    setLoading(true);
    fetchAnswerLibrary(session, query || undefined)
      .then(setEntries)
      .finally(() => setLoading(false));
  }, [session, query]);

  if (!session) return <p className="text-sm text-slate-600">Please sign in.</p>;

  return (
    <div>
      <PageHeader title="Answer library" subtitle="Reusable approved answers with evidence snapshots." />
      <input
        className="aq-input mb-6 max-w-md"
        placeholder="Search questions…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {loading && <LoadingState label="Loading library…" />}
      {!loading && entries.length === 0 && (
        <EmptyState
          title="No library entries yet"
          description="Approved answers can be saved to the library for reuse on similar questions."
        />
      )}
      <div className="grid gap-3">
        {entries.map((entry) => (
          <article key={entry.id} className="aq-card aq-card-p aq-card-hover">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="font-medium text-slate-900 line-clamp-2">{entry.question_text}</p>
                <p className="text-sm text-slate-600 mt-2 line-clamp-2">{entry.answer_text}</p>
              </div>
              <div className="text-right shrink-0 space-y-1">
                <StatusBadge status={entry.status} />
                <div className="text-xs text-slate-500">Reused {entry.reuse_count}×</div>
              </div>
            </div>
            <Link to={`/answer-library/${entry.id}`} className="aq-link text-sm mt-3 inline-block">
              View details
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
