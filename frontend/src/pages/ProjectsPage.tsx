import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SourceCreateFields } from "../components/projects/SourceCreateFields";
import { PageHeader, EmptyState, LoadingState, ErrorState, Modal } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { createProject, fetchProjectSummaries } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useProjectContext } from "../lib/projectContext";
import { canEditContent } from "../lib/roles";
import { buildInitialSourcePayload, readSourceForm } from "../lib/sourceForm";

type Summary = {
  id: string;
  name: string;
  description?: string;
  questionnaire_count: number;
  source_count: number;
  evidence_item_count: number;
  pending_review_count: number;
  potentially_stale_count: number;
};

export default function ProjectsPage() {
  const { session, reloadProjects } = useProjectContext();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const editable = user ? canEditContent(user.role) : false;
  const [rows, setRows] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  async function load() {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      setRows(await fetchProjectSummaries(session));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session?.organizationId]);

  async function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!session) return;
    setCreating(true);
    const form = new FormData(e.currentTarget);
    const sourceValues = readSourceForm(form);
    const initial_source = buildInitialSourcePayload(sourceValues);
    try {
      const project = await createProject(session, {
        name: String(form.get("name")),
        description: String(form.get("description") || "") || undefined,
        initial_source,
      });
      toast.push(initial_source ? "Project and source created." : "Project created.");
      setShowCreate(false);
      await reloadProjects();
      navigate(`/projects/${project.id}`);
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Failed to create project", "err");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Projects"
        subtitle="Create a project with its source code, then run questionnaires and evidence-backed answers."
        actions={
          editable ? (
            <button type="button" onClick={() => setShowCreate(true)} className="aq-btn-primary">
              Create project
            </button>
          ) : undefined
        }
      />
      {loading && <LoadingState label="Loading projects…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && rows.length === 0 && (
        <EmptyState
          title="No projects yet"
          description="Create a project with name, description, and source code in one step."
          action={
            editable ? (
              <button type="button" onClick={() => setShowCreate(true)} className="aq-btn-primary">
                Create project
              </button>
            ) : undefined
          }
        />
      )}
      {!loading && rows.length > 0 && (
        <div className="aq-table-wrap">
          <table className="aq-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Sources</th>
                <th>Questionnaires</th>
                <th>Evidence</th>
                <th>Review</th>
                <th>Stale</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/projects/${p.id}`} className="font-medium text-slate-900 hover:text-info-text">
                      {p.name}
                    </Link>
                    {p.description && <div className="text-xs text-slate-500">{p.description}</div>}
                  </td>
                  <td className="tabular-nums">{p.source_count}</td>
                  <td className="tabular-nums">{p.questionnaire_count}</td>
                  <td className="tabular-nums">{p.evidence_item_count}</td>
                  <td className="tabular-nums">{p.pending_review_count}</td>
                  <td className="tabular-nums">{p.potentially_stale_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <Modal title="Create project" onClose={() => setShowCreate(false)} wide>
          <form onSubmit={onCreate} className="space-y-4">
            <div className="space-y-3">
              <label className="block text-sm font-medium text-slate-800">
                Project name
                <input name="name" required placeholder="Project name" className="aq-input mt-1" />
              </label>
              <label className="block text-sm font-medium text-slate-800">
                Description
                <textarea
                  name="description"
                  placeholder="Description (optional)"
                  className="aq-textarea min-h-20 mt-1"
                />
              </label>
            </div>
            <SourceCreateFields defaultSourceName="" />
            <div className="flex gap-2 justify-end pt-2">
              <button type="button" className="aq-btn-ghost" onClick={() => setShowCreate(false)} disabled={creating}>
                Cancel
              </button>
              <button type="submit" className="aq-btn-primary" disabled={creating}>
                {creating ? "Creating…" : "Create project"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      <p className="text-xs text-slate-500 mt-4">
        Tip: use the project selector in the sidebar to filter dashboard and list views.{" "}
        <Link to="/questionnaires" className="aq-link text-xs">
          Open questionnaires
        </Link>
      </p>
    </div>
  );
}
