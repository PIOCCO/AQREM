import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useToast } from "../components/ui/Toast";
import { StatusBadge } from "../components/ui/Badges";
import { PageHeader, EmptyState, LoadingState, ErrorState, Modal } from "../components/ui/States";
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
            <button type="button" onClick={() => setShowCreate(true)} className="aq-btn-primary">
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
              <button type="button" onClick={() => setShowCreate(true)} className="aq-btn-primary">
                New questionnaire
              </button>
            ) : undefined
          }
        />
      )}
      {rows.length > 0 && (
        <div className="aq-table-wrap">
          <table className="aq-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Questions</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="font-medium max-w-xs truncate">{row.name}</td>
                  <td>
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="tabular-nums">{row.question_count}</td>
                  <td>
                    <Link className="aq-link text-sm" to={`/questionnaires/${row.id}`}>
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && editable && (
        <Modal title="New questionnaire" onClose={() => setShowCreate(false)} wide>
          <form onSubmit={onCreate} className="space-y-3">
            <input name="name" required placeholder="Questionnaire name" className="aq-input" />
            <select name="project_id" className="aq-select" defaultValue={projectId ?? ""}>
              <option value="">Select project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input name="recipient" placeholder="Recipient (optional)" className="aq-input" />
            <textarea name="description" placeholder="Description (optional)" className="aq-textarea min-h-16" />
            <label className="block text-sm text-slate-600">
              Upload questions (CSV/XLSX)
              <input name="file" type="file" accept=".csv,.xlsx,.xls" className="mt-1 block w-full text-sm" />
            </label>
            <div className="flex gap-2 justify-end pt-2">
              <button type="button" className="aq-btn-ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="aq-btn-primary">
                Create
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
