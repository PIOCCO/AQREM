import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StatusBadge } from "../ui/Badges";
import { EmptyState, ErrorState, LoadingState, Modal } from "../ui/States";
import { useToast } from "../ui/Toast";
import {
  fetchSources,
  triggerSourceSync,
  uploadSourceFiles,
  type AuthSession,
} from "../../lib/api";
import { createSourceForProject, readSourceForm } from "../../lib/sourceForm";
import { pollSyncJob } from "../../lib/syncJobPoll";
import { SourceCreateFields } from "./SourceCreateFields";

type SourceRow = {
  id: string;
  name: string;
  source_type: string;
  status: string;
  project_id?: string;
  config: Record<string, unknown>;
  created_at: string;
};

type Props = {
  session: AuthSession;
  projectId: string;
  editable: boolean;
  title?: string;
};

export default function ProjectSourcesSection({
  session,
  projectId,
  editable,
  title = "Source code",
}: Props) {
  const toast = useToast();
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchSources(session, projectId);
      setSources(
        (Array.isArray(rows) ? rows : []).filter(
          (s: SourceRow) => s.project_id === projectId,
        ),
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

  async function onAddSource(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!editable) return;
    const form = new FormData(e.currentTarget);
    const values = readSourceForm(form);
    if (!values.sourceName) {
      toast.push("Enter a source name.", "err");
      return;
    }
    try {
      await createSourceForProject(session, projectId, values);
      toast.push("Source connected.");
      setShowCreate(false);
      await load();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Failed to add source", "err");
    }
  }

  async function onSync(sourceId: string) {
    if (!editable) return;
    setSyncingId(sourceId);
    setJobStatus("queued");
    try {
      const job = await triggerSourceSync(session, sourceId);
      toast.push("Indexing started…");
      const final = await pollSyncJob(session, job.id, setJobStatus);
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
    if (!editable || !files?.length) return;
    setSyncingId(sourceId);
    try {
      const job = await uploadSourceFiles(session, sourceId, Array.from(files));
      toast.push("Upload queued; indexing…");
      await pollSyncJob(session, job.id, setJobStatus);
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
    <section className="mt-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-section-title text-slate-900">{title}</h2>
        {editable && (
          <button type="button" onClick={() => setShowCreate(true)} className="aq-btn-secondary text-sm">
            Add source
          </button>
        )}
      </div>
      {syncingId && jobStatus && (
        <p className="mb-4 text-sm text-slate-600">Indexing status: {jobStatus.replaceAll("_", " ")}…</p>
      )}
      {loading && <LoadingState label="Loading sources…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && sources.length === 0 && (
        <EmptyState
          title="No source code connected"
          description="Add a repository, folder path, or document upload to index evidence for this project."
          action={
            editable ? (
              <button type="button" onClick={() => setShowCreate(true)} className="aq-btn-primary">
                Add source
              </button>
            ) : undefined
          }
        />
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {sources.map((source) => (
          <article key={source.id} className="aq-card aq-card-p">
            <div className="flex items-start justify-between gap-2 mb-2">
              <h3 className="font-semibold text-slate-900">{source.name}</h3>
              <span className="text-xs uppercase tracking-wide text-slate-500">
                {source.source_type.replaceAll("_", " ")}
              </span>
            </div>
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
                to={`/evidence?source=${source.id}&project=${projectId}`}
                className="aq-btn-secondary text-sm py-1.5"
              >
                View evidence
              </Link>
            </div>
          </article>
        ))}
      </div>

      {showCreate && editable && (
        <Modal title="Add source to project" onClose={() => setShowCreate(false)} wide>
          <form onSubmit={onAddSource} className="space-y-3">
            <SourceCreateFields />
            <div className="flex gap-2 justify-end pt-2">
              <button type="button" className="aq-btn-ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
              <button type="submit" className="aq-btn-primary">
                Add source
              </button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
