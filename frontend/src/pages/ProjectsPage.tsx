import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, EmptyState, LoadingState, ErrorState } from "../components/ui/States";
import { createProject, fetchProjectSummaries } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

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
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium"
          >
            Create project
          </button>
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
              className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm"
            >
              Create project
            </button>
          }
        />
      )}
      {!loading && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Project</th>
                <th className="px-4 py-3 font-medium">Questionnaires</th>
                <th className="px-4 py-3 font-medium">Sources</th>
                <th className="px-4 py-3 font-medium">Evidence</th>
                <th className="px-4 py-3 font-medium">Review</th>
                <th className="px-4 py-3 font-medium">Stale</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{p.name}</div>
                    {p.description && <div className="text-xs text-slate-500">{p.description}</div>}
                  </td>
                  <td className="px-4 py-3">{p.questionnaire_count}</td>
                  <td className="px-4 py-3">{p.source_count}</td>
                  <td className="px-4 py-3">{p.evidence_item_count}</td>
                  <td className="px-4 py-3">{p.pending_review_count}</td>
                  <td className="px-4 py-3">{p.potentially_stale_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4 z-50">
          <form
            onSubmit={onCreate}
            className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg space-y-3"
          >
            <h2 className="text-lg font-semibold">New project</h2>
            <input
              name="name"
              required
              placeholder="Project name"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <textarea
              name="description"
              placeholder="Description (optional)"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-20"
            />
            <div className="flex gap-2 justify-end">
              <button type="button" className="px-3 py-2 text-sm" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm">
                Create
              </button>
            </div>
          </form>
        </div>
      )}

      <p className="text-xs text-slate-500 mt-4">
        Tip: use the project selector in the sidebar to filter dashboard and list views.{" "}
        <Link to="/questionnaires" className="text-blue-600 hover:underline">
          Open questionnaires
        </Link>
      </p>
    </div>
  );
}
