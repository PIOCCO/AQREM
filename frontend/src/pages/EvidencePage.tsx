import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { EvidenceStrengthBadge } from "../components/ui/Badges";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchEvidence, fetchSources } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

type EvidenceRow = {
  id: string;
  file_path: string;
  content: string;
  evidence_strength?: string;
  commit_hash?: string;
  repository?: string;
  line_start?: number;
  line_end?: number;
};

export default function EvidencePage() {
  const { session, projectId } = useProjectContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<EvidenceRow[]>([]);
  const [sources, setSources] = useState<Array<{ id: string; name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const search = searchParams.get("search") ?? "";
  const sourceId = searchParams.get("source") ?? "";

  async function load() {
    if (!session) return;
    setLoading(true);
    try {
      const [evidence, src] = await Promise.all([
        fetchEvidence(session, {
          project_id: projectId ?? undefined,
          source_id: sourceId || undefined,
          search: search || undefined,
          limit: 50,
        }),
        fetchSources(session),
      ]);
      setItems(evidence);
      setSources(src.map((s: { id: string; name: string }) => ({ id: s.id, name: s.name })));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load evidence");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session?.organizationId, projectId, search, sourceId]);

  return (
    <div>
      <PageHeader title="Evidence" subtitle="Search indexed evidence used for answers and citations." />
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          className="aq-input flex-1"
          placeholder="Search evidence…"
          value={search}
          onChange={(e) => {
            const next = new URLSearchParams(searchParams);
            if (e.target.value) next.set("search", e.target.value);
            else next.delete("search");
            setSearchParams(next);
          }}
        />
        <select
          className="aq-select sm:max-w-xs"
          value={sourceId}
          onChange={(e) => {
            const next = new URLSearchParams(searchParams);
            if (e.target.value) next.set("source", e.target.value);
            else next.delete("source");
            setSearchParams(next);
          }}
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      {loading && <LoadingState label="Loading evidence…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState
          title="No evidence indexed yet"
          description="Connect a source and run indexing to populate your knowledge base."
        />
      )}
      <div className="space-y-3">
        {items.map((item) => (
          <article key={item.id} className="aq-card aq-card-p">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <h2 className="font-medium text-slate-900 font-mono text-sm break-all">{item.file_path}</h2>
              <EvidenceStrengthBadge strength={item.evidence_strength} />
            </div>
            <p className="text-xs text-slate-500 mb-2 font-mono">
              {item.repository && `${item.repository} · `}
              {item.commit_hash && `commit ${item.commit_hash.slice(0, 8)} · `}
              {item.line_start != null && `lines ${item.line_start}${item.line_end ? `–${item.line_end}` : ""}`}
            </p>
            <p className="text-sm text-slate-700 line-clamp-3 whitespace-pre-wrap font-mono">{item.content}</p>
            <Link to={`/evidence/${item.id}`} className="aq-link inline-block mt-3 text-sm">
              View evidence
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
