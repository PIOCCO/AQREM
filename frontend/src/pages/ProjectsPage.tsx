import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CreateProjectDialog } from "../components/projects/CreateProjectDialog";
import { PageHeader, EmptyState, LoadingState, ErrorState } from "../components/ui/States";
import { fetchProjectSummaries } from "../lib/api";
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
  const navigate = useNavigate();
  const editable = user?.role ? canEditContent(user.role) : false;
  const [rows, setRows] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const createBtnRef = useRef<HTMLButtonElement>(null);

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

  return (
    <div>
      <PageHeader
        title="Projects"
        subtitle="Create a project with its source code, then run questionnaires and evidence-backed answers."
        actions={
          editable ? (
            <button ref={createBtnRef} type="button" onClick={() => setShowCreate(true)} className="aq-btn-primary">
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
          description="Create a project and connect at least one source to start answering questionnaires."
          action={
            editable ? (
              <button type="button" onClick={() => setShowCreate(true)} className="aq-btn-primary">
                Create project
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
                <th>Project</th>
                <th>Sources</th>
                <th>Questionnaires</th>
                <th>Evidence</th>
                <th>Pending review</th>
                <th>Potentially stale</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td className="font-medium">
                    <Link to={`/projects/${p.id}`} className="aq-link">
                      {p.name}
                    </Link>
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

      {showCreate && session ? (
        <CreateProjectDialog
          open={showCreate}
          onClose={() => setShowCreate(false)}
          session={session}
          returnFocusRef={createBtnRef}
          onCreated={async (project) => {
            await reloadProjects();
            navigate(`/projects/${project.id}`);
          }}
        />
      ) : null}

      <p className="text-xs text-fg-muted mt-4">
        Tip: use the project selector in the sidebar to filter dashboard and list views.{" "}
        <Link to="/questionnaires" className="aq-link text-xs">
          Open questionnaires
        </Link>
      </p>
    </div>
  );
}
