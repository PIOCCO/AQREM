import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import NewQuestionnaireDialog from "../components/questionnaires/NewQuestionnaireDialog";
import { CreateProjectDialog } from "../components/projects/CreateProjectDialog";
import { StatusBadge } from "../components/ui/Badges";
import { PageHeader, EmptyState, LoadingState, ErrorState } from "../components/ui/States";
import { fetchQuestionnaires } from "../lib/api";
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
  const { projectId, projects, reloadProjects } = useProjectContext();
  const [rows, setRows] = useState<Questionnaire[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [pendingProjectId, setPendingProjectId] = useState<string | null>(null);
  const createBtnRef = useRef<HTMLButtonElement>(null);
  const editable = user?.role ? canEditContent(user.role) : false;

  async function load() {
    if (!session) return;
    setLoading(true);
    try {
      const data = await fetchQuestionnaires(session, projectId);
      setRows(data);
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

  useEffect(() => {
    if (pendingProjectId && projects.some((p) => p.id === pendingProjectId)) {
      setShowCreate(true);
      setPendingProjectId(null);
    }
  }, [pendingProjectId, projects]);

  return (
    <div>
      <PageHeader
        title="Questionnaires"
        subtitle="Upload customer or vendor questionnaires, generate evidence-backed answers, and export results."
        actions={
          editable ? (
            <button
              ref={createBtnRef}
              type="button"
              onClick={() => setShowCreate(true)}
              className="aq-btn-primary"
              data-testid="new-questionnaire-trigger"
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

      {showCreate && editable && session ? (
        <NewQuestionnaireDialog
          open={showCreate}
          onClose={() => setShowCreate(false)}
          session={session}
          projects={projects}
          defaultProjectId={projectId}
          returnFocusRef={createBtnRef}
          onRequestCreateProject={() => {
            setShowCreate(false);
            setShowCreateProject(true);
          }}
        />
      ) : null}

      {showCreateProject && session ? (
        <CreateProjectDialog
          open={showCreateProject}
          session={session}
          onClose={() => {
            setShowCreateProject(false);
            setShowCreate(true);
          }}
          onCreated={async (project) => {
            await reloadProjects();
            setPendingProjectId(project.id);
            setShowCreateProject(false);
          }}
          returnFocusRef={createBtnRef}
        />
      ) : null}

      <p className="text-xs text-fg-muted mt-4">
        <Link to="/projects" className="aq-link text-xs">
          Manage projects
        </Link>
      </p>
    </div>
  );
}
