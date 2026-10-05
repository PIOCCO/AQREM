import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchAnswerLibraryEntry, loadSession, validateLibraryEntry } from "../lib/api";

export default function AnswerLibraryDetailPage() {
  const { entryId } = useParams();
  const session = loadSession();
  const [entry, setEntry] = useState<any>(null);
  const [validation, setValidation] = useState<any>(null);

  useEffect(() => {
    if (!session || !entryId) return;
    fetchAnswerLibraryEntry(session, entryId).then(setEntry);
    validateLibraryEntry(session, entryId).then(setValidation);
  }, [session, entryId]);

  if (!entry) return <p>Loading…</p>;

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Answer details</h1>
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-medium mb-2">Question</h2>
        <p>{entry.question_text}</p>
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-medium mb-2">Approved answer</h2>
        <p className="whitespace-pre-wrap">{entry.answer_text}</p>
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium">Evidence validation</h2>
          <span
            className={`text-xs px-2 py-1 rounded-full ${
              validation?.valid ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
            }`}
          >
            {validation?.valid ? "Evidence valid" : "Needs review"}
          </span>
        </div>
        <ul className="space-y-2 text-sm">
          {(entry.evidence ?? []).map((ev: any, idx: number) => (
            <li key={idx} className="rounded-lg bg-slate-50 p-3">
              <div className="font-medium">{ev.file_path}</div>
              <div className="text-xs text-slate-500">hash {ev.snapshot_content_hash.slice(0, 12)}…</div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
