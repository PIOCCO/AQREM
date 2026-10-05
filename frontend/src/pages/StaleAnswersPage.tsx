import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStaleAnswers, loadSession } from "../lib/api";

type StaleItem = {
  answer_id: string;
  question_text: string;
  project_name?: string;
  status: string;
  stale_detected_at?: string;
  changed_evidence_count: number;
};

export default function StaleAnswersPage() {
  const session = loadSession();
  const [items, setItems] = useState<StaleItem[]>([]);
  const [search, setSearch] = useState("");
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!session) return;
    fetchStaleAnswers(session, { search: search || undefined }).then((data) => {
      setItems(data.items);
      setTotal(data.total);
    });
  }, [session, search]);

  if (!session) return <p>Please sign in.</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Potentially Stale Answers</h1>
      <p className="text-slate-600 mb-4">{total} answers require review</p>
      <input
        className="mb-6 w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 text-sm"
        placeholder="Search questions…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.answer_id} className="rounded-xl border border-amber-200 bg-white p-4">
            <p className="font-medium">{item.question_text}</p>
            <p className="text-sm text-slate-500 mt-1">
              Project: {item.project_name ?? "—"} · Evidence changes: {item.changed_evidence_count}
            </p>
            <p className="text-xs text-amber-700 mt-2">Status: Potentially Stale</p>
            <Link
              to={`/stale-answers/${item.answer_id}`}
              className="inline-block mt-3 text-sm text-blue-600 hover:underline"
            >
              Review
            </Link>
          </div>
        ))}
        {!items.length && <p className="text-slate-500">No stale answers right now.</p>}
      </div>
    </div>
  );
}
