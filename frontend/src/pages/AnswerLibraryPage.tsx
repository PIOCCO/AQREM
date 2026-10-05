import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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

  useEffect(() => {
    if (!session) return;
    fetchAnswerLibrary(session, query || undefined).then(setEntries);
  }, [session, query]);

  if (!session) return <p>Please sign in.</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Answer Library</h1>
      <p className="text-slate-600 mb-4">Reusable approved answers with evidence snapshots.</p>
      <input
        className="mb-6 w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 text-sm"
        placeholder="Search questions…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="grid gap-3">
        {entries.map((entry) => (
          <div key={entry.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium">{entry.question_text}</p>
                <p className="text-sm text-slate-600 mt-2 line-clamp-2">{entry.answer_text}</p>
              </div>
              <div className="text-right text-xs text-slate-500 shrink-0">
                <div className="capitalize">{entry.status.replaceAll("_", " ")}</div>
                <div className="mt-1">Reused {entry.reuse_count}×</div>
              </div>
            </div>
            <Link to={`/answer-library/${entry.id}`} className="text-sm text-blue-600 hover:underline mt-3 inline-block">
              View details
            </Link>
          </div>
        ))}
        {!entries.length && <p className="text-slate-500">No approved library entries yet.</p>}
      </div>
    </div>
  );
}
