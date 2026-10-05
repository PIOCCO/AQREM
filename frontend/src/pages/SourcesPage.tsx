import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useToast } from "../components/ui/Toast";
import { StatusBadge } from "../components/ui/Badges";
import { PageHeader, EmptyState, LoadingState, ErrorState, Modal } from "../components/ui/States";
import {
  createSource,
  fetchSources,
  fetchSyncJob,
  triggerSourceSync,
  uploadSourceFiles,
  connectGithubRepo,
} from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useProjectContext } from "../lib/projectContext";
import { canEditContent } from "../lib/roles";

type SourceRow = {
  id: string;
  name: string;
  source_type: string;
  status: string;
  project_id?: string;
  config: Record<string, unknown>;
  created_at: string;
};

async function pollJob(
  session: NonNullable<ReturnType<typeof useAuth>["session"]>,
  jobId: string,
  onUpdate: (status: string) => void,
) {
  for (let i = 0; i < 120; i++) {
    const job = await fetchSyncJob(session, jobId);
    onUpdate(job.status);
    if (job.status === "completed" || job.status === "failed") return job;
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Sync timed out. Check Activity or retry.");
}

export default function SourcesPage() {
  const { session, user } = useAuth();
  const { projectId, projects } = useProjectContext();
  const toast = useToast();
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  const editable = user ? canEditContent(user.role) : false;

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchSources(session);
      setSources(
        projectId ? rows.filter((s: SourceRow) => s.project_id === projectId || !s.project_id) : rows,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load sources");
    } finally {
      setLoading(false);
    }
  }, [session, projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function onCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!session || !editable) return;
    const form = new FormData(e.currentTarget);
    const sourceType = String(form.get("source_type"));
    const config: Record<string, unknown> = {};
    const demoPath = String(form.get("demo_path") || "").trim();
    if (demoPath) config.demo_path = demoPath;

    try {
      const created = await createSource(session, {
        name: String(form.get("name")),
        source_type: sourceType,
        project_id: (form.get("project_id") as string) || projectId || undefined,
        config,
      });

      if (sourceType === "github") {
        const repo = String(form.get("repository") || "").trim();
        if (repo) {
          await connectGithubRepo(session, {
            source_id: created.id,
            repository_full_name: repo,
            branch: String(form.get("branch") || "main"),
            access_token: String(form.get("github_token") || "") || undefined,
          });
        }
      }

      toast.push("Source connected.");
      setShowCreate(false);
      await load();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Failed to create source", "err");
    }
  }

  async function onSync(sourceId: string) {
    if (!session || !editable) return;
    setSyncingId(sourceId);
    setJobStatus("queued");
    try {
      const job = await triggerSourceSync(session, sourceId);
      toast.push("Indexing started…");
      const final = await pollJob(session, job.id, setJobStatus);
      if (final.status === "failed") {
        toast.push(final.error_message || "Indexing failed.", "err");
      } else {
        toast.push("Indexing completed.");
      }
      await load();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Sync failed", "err");
    } finally {
      setSyncingId(null);
      setJobStatus(null);
    }
  }

  async function onUploadFiles(sourceId: string, files: FileList | null) {
    if (!session || !editable || !files?.length) return;
    setSyncingId(sourceId);
    try {
      const job = await uploadSourceFiles(session, sourceId, Array.from(files));
      toast.push("Upload queued; indexing…");
      await pollJob(session, job.id, setJobStatus);
      toast.push("Files indexed.");
      await load();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Upload failed", "err");
    } finally {
      setSyncingId(null);
      setJobStatus(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="Sources"
        subtitle="Connect repositories or document uploads, then index evidence for questionnaires."
        actions={
          editable ? (
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="aq-btn-primary"
            >
              Add source
            </button>
          ) : undefined
        }
      />
      {syncingId && jobStatus && (
        <p className="mb-4 text-sm text-slate-600">Indexing status: {jobStatus.replaceAll("_", " ")}…</p>
      )}
      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && sources.length === 0 && (
        <EmptyState
          title="No evidence sources connected"
          description="Add a folder archive, file upload source, or GitHub repository to build your knowledge base."
          action={
            editable ? (
              <button
                type="button"
                onClick={() => setShowCreate(true)}
                className="aq-btn-primary"
              >
                Add source
              </button>
            ) : undefined
          }
        />
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {sources.map((source) => {
          const projectName = projects.find((p) => p.id === source.project_id)?.name;
          return (
            <article key={source.id} className="aq-card aq-card-p aq-card-hover">
              <div className="flex items-start justify-between gap-2 mb-2">
                <h2 className="font-semibold text-slate-900">{source.name}</h2>
                <span className="text-xs uppercase tracking-wide text-slate-500">
                  {source.source_type.replaceAll("_", " ")}
                </span>
              </div>
              {projectName && <p className="text-xs text-slate-500 mb-2">Project: {projectName}</p>}
              <div className="mb-3">
                <StatusBadge status={source.status} />
              </div>
              {typeof source.config?.demo_path === "string" && (
                <p className="text-xs font-mono text-slate-600 mb-2">Path: {source.config.demo_path}</p>
              )}
              {source.source_type === "github" && typeof source.config?.repository_full_name === "string" && (
                <p className="text-xs font-mono text-slate-600 mb-2">{source.config.repository_full_name}</p>
              )}
              <div className="flex flex-wrap gap-2 mt-3">
                {editable && (
                  <>
                    <button
                      type="button"
                      disabled={syncingId === source.id}
                      onClick={() => onSync(source.id)}
                      className="aq-btn-secondary text-sm py-1.5 disabled:opacity-50"
                    >
                      {syncingId === source.id ? "Syncing…" : "Sync / re-index"}
                    </button>
                    {source.source_type === "file_upload" && (
                      <label className="aq-btn-secondary text-sm py-1.5 cursor-pointer">
                        Upload files
                        <input
                          type="file"
                          multiple
                          className="hidden"
                          onChange={(e) => onUploadFiles(source.id, e.target.files)}
                        />
                      </label>
                    )}
                  </>
                )}
                <Link
                  to={`/evidence?source=${source.id}`}
                  className="aq-btn-secondary text-sm py-1.5"
                >
                  View evidence
                </Link>
              </div>
            </article>
          );
        })}
      </div>

      {showCreate && editable && (
        <Modal title="Add source" onClose={() => setShowCreate(false)} wide>
          <form onSubmit={onCreate} className="space-y-3">
            <input name="name" required placeholder="Source name" className="aq-input" />
            <select name="project_id" className="aq-select" defaultValue={projectId ?? ""}>
              <option value="">No project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select name="source_type" className="aq-select" defaultValue="folder_archive">
              <option value="folder_archive">Folder archive (demo path)</option>
              <option value="file_upload">Document upload</option>
              <option value="github">GitHub repository</option>
            </select>
            <input
              name="demo_path"
              placeholder="Folder path on server (folder_archive), e.g. /workspace/tests/fixtures/demo_saas_repo"
              className="aq-input"
            />
            <input name="repository" placeholder="GitHub owner/repo (github only)" className="aq-input" />
            <input name="branch" placeholder="Branch (default main)" className="aq-input" />
            <input name="github_token" type="password" placeholder="GitHub token (dev only, optional)" className="aq-input" />
            <div className="flex gap-2 justify-end pt-2">
              <button type="button" className="aq-btn-ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="aq-btn-primary">
                Create & connect
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
