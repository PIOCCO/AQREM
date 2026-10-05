import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchSources } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

type SourceRow = {
  id: string;
  name: string;
  source_type: string;
  status: string;
  project_id?: string;
  config: Record<string, unknown>;
};

function sourceTypeLabel(type: string) {
  return type.replaceAll("_", " ");
}

export default function SourcesPage() {
  const { session, projectId, projects } = useProjectContext();
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!session) return;
    setLoading(true);
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
  }

  useEffect(() => {
    load();
  }, [session?.organizationId, projectId]);

  return (
    <div>
      <PageHeader
        title="Sources"
        subtitle="Connect repositories, upload documents, or folder archives to build your evidence base."
      />
      {loading && <LoadingState />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && sources.length === 0 && (
        <EmptyState
          title="No evidence sources connected"
          description="Connect GitHub or upload company documents to index evidence for questionnaires."
        />
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {sources.map((source) => {
          const projectName = projects.find((p) => p.id === source.project_id)?.name;
          return (
            <article key={source.id} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-start justify-between gap-2 mb-2">
                <h2 className="font-semibold text-slate-900">{source.name}</h2>
                <span className="text-xs uppercase tracking-wide text-slate-500">
                  {sourceTypeLabel(source.source_type)}
                </span>
              </div>
              {projectName && <p className="text-xs text-slate-500 mb-2">Project: {projectName}</p>}
              <p className="text-sm text-slate-700 mb-3">
                Status:{" "}
                <span className="font-medium capitalize">{source.status.replaceAll("_", " ")}</span>
              </p>
              {source.source_type === "github" &&
              typeof source.config?.repository_full_name === "string" ? (
                <p className="text-xs text-slate-600 font-mono mb-2">
                  {source.config.repository_full_name} · branch{" "}
                  {typeof source.config.branch === "string" ? source.config.branch : "main"}
                </p>
              ) : null}
              <p className="text-xs text-slate-500">
                Manage indexing via API or worker sync jobs for this source type.
              </p>
            </article>
          );
        })}
      </div>
    </div>
  );
}
