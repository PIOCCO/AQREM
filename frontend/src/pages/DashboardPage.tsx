import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMetrics, loadSession } from "../lib/api";

const cards = [
  ["questions", "Questions"],
  ["approved_answers", "Approved Answers"],
  ["pending_review", "Pending Review"],
  ["insufficient_evidence", "Insufficient Evidence"],
  ["potentially_stale", "Potentially Stale"],
] as const;

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const session = loadSession();
    if (!session) {
      setError("Sign in to view dashboard metrics.");
      return;
    }
    fetchMetrics(session)
      .then(setMetrics)
      .catch(() => setError("Unable to load dashboard metrics."));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Dashboard</h1>
      <p className="text-slate-600 mb-6">
        Manage company evidence and turn it into verified responses.
      </p>
      {error && <p className="text-sm text-amber-700 mb-4">{error}</p>}
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {cards.map(([key, label]) => {
          const content = (
            <>
              <div className="text-2xl font-semibold">{metrics?.[key] ?? "—"}</div>
              <div className="text-sm text-slate-500">{label}</div>
            </>
          );
          if (key === "potentially_stale") {
            return (
              <Link
                key={key}
                to="/stale-answers"
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-amber-300"
              >
                {content}
              </Link>
            );
          }
          return (
            <div key={key} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              {content}
            </div>
          );
        })}
      </div>
    </div>
  );
}
