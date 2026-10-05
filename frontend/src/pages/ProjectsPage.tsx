import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, EmptyState, LoadingState, ErrorState, Modal } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { createProject, fetchProjectSummaries } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useProjectContext } from "../lib/projectContext";
import { canEditContent } from "../lib/roles";

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
  const toast = useToast();
  const editable = user ? canEditContent(user.role) : false;
  const [rows, setRows] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

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
    const form = new FormData(e.currentTarget);
    await createProject(session, {
      name: String(form.get("name")),
      description: String(form.get("description") || "") || undefined,
    });
    toast.push("Project created.");
    setShowCreate(false);
    await reloadProjects();
    await load();
  }

  return (
    <div>
      <PageHeader
        title="Projects"
        subtitle="Organize questionnaires, sources, and evidence by initiative or product."
        actions={
          editable ? (
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="aq-btn-primary"
            >
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
          description="Create your first project to start organizing questionnaires and evidence."
          action={
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="aq-btn-primary"
            >
              Create project
            </button>
          }
        />
      )}
      {!loading && rows.length > 0 && (
        <div className="aq-table-wrap">
          <table className="aq-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Questionnaires</th>
                <th>Sources</th>
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
                  <td className="tabular-nums">{p.questionnaire_count}</td>
                  <td className="tabular-nums">{p.source_count}</td>
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
        <Modal title="New project" onClose={() => setShowCreate(false)}>
          <form onSubmit={onCreate} className="space-y-3">
            <input name="name" required placeholder="Project name" className="aq-input" />
            <textarea name="description" placeholder="Description (optional)" className="aq-textarea min-h-20" />
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

      <p className="text-xs text-slate-500 mt-4">
        Tip: use the project selector in the sidebar to filter dashboard and list views.{" "}
        <Link to="/questionnaires" className="aq-link text-xs">
          Open questionnaires
        </Link>
      </p>
    </div>
  );
}
