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

const PAGE_SIZE = 50;

export default function EvidencePage() {
  const { session, projectId, setProjectId } = useProjectContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<EvidenceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sources, setSources] = useState<Array<{ id: string; name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const search = searchParams.get("search") ?? "";
  const sourceId = searchParams.get("source") ?? "";
  const projectParam = searchParams.get("project") ?? "";

  useEffect(() => {
    if (projectParam && projectParam !== projectId) {
      setProjectId(projectParam);
    }
  }, [projectParam, projectId, setProjectId]);

  async function load(append = false, nextOffset = 0) {
    if (!session) return;
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const [evidence, src] = await Promise.all([
        fetchEvidence(session, {
          project_id: projectId ?? undefined,
          source_id: sourceId || undefined,
          search: search || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        }),
        fetchSources(session, projectId),
      ]);
      const rows = Array.isArray(evidence.items) ? evidence.items : [];
      setTotal(typeof evidence.total === "number" ? evidence.total : rows.length);
      setOffset(nextOffset);
      setItems((prev) => (append ? [...prev, ...rows] : rows) as EvidenceRow[]);
      setSources(src.map((s: { id: string; name: string }) => ({ id: s.id, name: s.name })));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load evidence");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    load(false, 0);
  }, [session?.organizationId, session?.token, projectId, search, sourceId]);

  const hasMore = items.length < total;

  return (
    <div>
      <PageHeader
        title="Evidence"
        subtitle={`${total} indexed items${projectId ? " in project scope" : ""}`}
      />
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
      {error && <ErrorState message={error} onRetry={() => load(false, 0)} />}
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
      {hasMore && !loading && (
        <button
          type="button"
          className="aq-btn-secondary mt-4"
          disabled={loadingMore}
          onClick={() => load(true, offset + PAGE_SIZE)}
        >
          {loadingMore ? "Loading…" : `Load more (${items.length} of ${total})`}
        </button>
      )}
    </div>
  );
}
