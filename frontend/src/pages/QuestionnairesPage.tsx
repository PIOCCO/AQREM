import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useToast } from "../components/ui/Toast";
import { PageHeader, EmptyState, LoadingState, ErrorState } from "../components/ui/States";
import { createQuestionnaire, fetchQuestionnaires, uploadQuestionnaireFile } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useProjectContext } from "../lib/projectContext";
import { canEditContent } from "../lib/roles";

type Questionnaire = {
  id: string;
  name: string;
  status: string;
  question_count: number;
  project_id?: string;
  recipient?: string;
};

export default function QuestionnairesPage() {
  const { session, user } = useAuth();
  const { projectId, projects } = useProjectContext();
  const toast = useToast();
  const navigate = useNavigate();
  const [rows, setRows] = useState<Questionnaire[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const editable = user ? canEditContent(user.role) : false;

  async function load() {
    if (!session) return;
    setLoading(true);
    try {
      const data = await fetchQuestionnaires(session);
      setRows(projectId ? data.filter((q: Questionnaire) => q.project_id === projectId) : data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load questionnaires");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session?.organizationId, projectId]);

  async function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!session || !editable) return;
    const form = new FormData(e.currentTarget);
    try {
      const qn = await createQuestionnaire(session, {
        name: String(form.get("name")),
        project_id: (form.get("project_id") as string) || projectId || undefined,
        recipient: String(form.get("recipient") || "") || undefined,
        description: String(form.get("description") || "") || undefined,
      });
      const file = (form.get("file") as File)?.size ? (form.get("file") as File) : null;
      if (file) {
        const result = await uploadQuestionnaireFile(session, qn.id, file);
        toast.push(`Questionnaire created with ${result.questions_extracted} questions.`);
      } else {
        toast.push("Questionnaire created. Upload questions from the detail page.");
      }
      setShowCreate(false);
      navigate(`/questionnaires/${qn.id}`);
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Failed to create questionnaire", "err");
    }
  }

  return (
    <div>
      <PageHeader
        title="Questionnaires"
        subtitle="Upload customer or vendor questionnaires, generate evidence-backed answers, and export results."
        actions={
          editable ? (
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium"
            >
              New questionnaire
            </button>
          ) : undefined
        }
      />
      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && rows.length === 0 && (
        <EmptyState
          title="No questionnaires yet"
          description="Create a questionnaire and upload a CSV or XLSX file with questions."
          action={
            editable ? (
              <button
                type="button"
                onClick={() => setShowCreate(true)}
                className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm"
              >
                New questionnaire
              </button>
            ) : undefined
          }
        />
      )}
      <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
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
          </tbody>
        </table>
      </div>

      {showCreate && editable && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
          <form onSubmit={onCreate} className="w-full max-w-lg rounded-xl bg-white p-6 shadow-lg space-y-3">
            <h2 className="text-lg font-semibold">New questionnaire</h2>
            <input name="name" required placeholder="Questionnaire name" className="w-full rounded-lg border px-3 py-2 text-sm" />
            <select name="project_id" className="w-full rounded-lg border px-3 py-2 text-sm" defaultValue={projectId ?? ""}>
              <option value="">Select project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input name="recipient" placeholder="Recipient (optional)" className="w-full rounded-lg border px-3 py-2 text-sm" />
            <textarea name="description" placeholder="Description (optional)" className="w-full rounded-lg border px-3 py-2 text-sm min-h-16" />
            <label className="block text-sm text-slate-600">
              Upload questions (CSV/XLSX)
              <input name="file" type="file" accept=".csv,.xlsx,.xls" className="mt-1 block w-full text-sm" />
            </label>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm">
                Create
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
