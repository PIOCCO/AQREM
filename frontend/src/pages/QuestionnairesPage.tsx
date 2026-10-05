import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchQuestionnaires, loadSession } from "../lib/api";

type Questionnaire = {
  id: string;
  name: string;
  status: string;
  question_count: number;
  recipient?: string;
};

export default function QuestionnairesPage() {
  const session = loadSession();
  const [rows, setRows] = useState<Questionnaire[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    fetchQuestionnaires(session)
      .then(setRows)
      .catch(() => setError("Unable to load questionnaires."));
  }, [session]);

  if (!session) {
    return <p className="text-slate-600">Please sign in first.</p>;
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-2">Questionnaires</h1>
      <p className="text-slate-600 mb-6">Upload, generate evidence-backed drafts, and review answers.</p>
      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Questions</th>
              <th className="text-left px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium">{row.name}</td>
                <td className="px-4 py-3 capitalize">{row.status.replaceAll("_", " ")}</td>
                <td className="px-4 py-3">{row.question_count}</td>
                <td className="px-4 py-3">
                  <Link className="text-blue-600 hover:underline" to={`/questionnaires/${row.id}`}>
                    Open
                  </Link>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  No questionnaires yet. Create one via the API to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
