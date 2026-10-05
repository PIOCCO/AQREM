import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { EvidenceStrengthBadge } from "../components/ui/Badges";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchEvidence, fetchSources } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";
import { capEvidenceListContent, truncateText } from "../lib/textPreview";
import { isUuid } from "../lib/uuid";

type EvidenceRow = {
  id: string;
  file_path?: string;
  content?: string;
  content_truncated?: boolean;
  evidence_strength?: string;
  commit_hash?: string;
  repository?: string;
  line_start?: number;
  line_end?: number;
};

const PAGE_SIZE = 25;

function sanitizeRow(raw: unknown): EvidenceRow | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as EvidenceRow;
  const id = row.id != null ? String(row.id) : "";
  if (!id) return null;
  const capped = capEvidenceListContent(row.content);
  return {
    ...row,
    id,
    content: capped.text,
    content_truncated: Boolean(row.content_truncated || capped.truncated),
  };
}

function normalizeEvidencePayload(data: unknown): { items: EvidenceRow[]; total: number } {
  if (Array.isArray(data)) {
    const items = data.map(sanitizeRow).filter((r): r is EvidenceRow => r != null);
    return { items, total: items.length };
  }
  if (data && typeof data === "object" && "items" in data) {
    const obj = data as { items?: unknown[]; total?: number };
    const items = Array.isArray(obj.items)
      ? obj.items.map(sanitizeRow).filter((r): r is EvidenceRow => r != null)
      : [];
    return { items, total: typeof obj.total === "number" ? obj.total : items.length };
  }
  return { items: [], total: 0 };
}

function scopedProjectId(projectFromUrl: string, projectId: string | null): string | undefined {
  if (projectFromUrl && isUuid(projectFromUrl)) return projectFromUrl;
  if (projectId && isUuid(projectId)) return projectId;
  return undefined;
}

export default function EvidencePage() {
  const { session, projectId } = useProjectContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<EvidenceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sources, setSources] = useState<Array<{ id: string; name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = searchParams.get("search") ?? "";
  const sourceParam = searchParams.get("source") ?? "";
  const sourceId = isUuid(sourceParam) ? sourceParam : "";
  const projectFromUrl = searchParams.get("project") ?? "";
  const scopeProjectId = scopedProjectId(projectFromUrl, projectId);

  const load = useCallback(
    async (append = false, nextOffset = 0) => {
      if (!session) {
        setLoading(false);
        return;
      }
      if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const evidenceRaw = await fetchEvidence(session, {
          project_id: scopeProjectId,
          source_id: sourceId || undefined,
          search: search || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        const evidence = normalizeEvidencePayload(evidenceRaw);
        setTotal(evidence.total);
        setOffset(nextOffset);
        setItems((prev) => (append ? [...prev, ...evidence.items] : evidence.items));
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load evidence");
        if (!append) setItems([]);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }

      fetchSources(session, scopeProjectId ?? null)
        .then((src) => {
          setSources(
            Array.isArray(src) ? src.map((s: { id: string; name: string }) => ({ id: s.id, name: s.name })) : [],
          );
        })
        .catch(() => setSources([]));
    },
    [session, scopeProjectId, sourceId, search],
  );

  useEffect(() => {
    load(false, 0);
  }, [load]);

  const hasMore = items.length < total;

  const subtitle = useMemo(
    () => `${total} indexed items${scopeProjectId ? " in project scope" : ""}`,
    [total, scopeProjectId],
  );

  return (
    <div>
      <PageHeader title="Evidence" subtitle={subtitle} />
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
        {items.map((item) => {
          const path = item.file_path ?? "Evidence item";
          const preview = truncateText(item.content ?? "", 800);
          const hash =
            item.commit_hash != null && item.commit_hash !== ""
              ? String(item.commit_hash)
              : null;
          return (
            <article key={item.id} className="aq-card aq-card-p">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <h2 className="font-medium text-slate-900 font-mono text-sm break-all">{path}</h2>
                <EvidenceStrengthBadge strength={item.evidence_strength} />
              </div>
              <p className="text-xs text-slate-500 mb-2 font-mono">
                {item.repository ? `${item.repository} · ` : null}
                {hash ? `commit ${hash.slice(0, 8)} · ` : null}
                {item.line_start != null
                  ? `lines ${item.line_start}${item.line_end != null ? `–${item.line_end}` : ""}`
                  : null}
              </p>
              <p className="text-sm text-slate-700 line-clamp-4 whitespace-pre-wrap break-all font-mono">{preview}</p>
              {item.content_truncated && (
                <p className="text-xs text-slate-500 mt-1">Preview truncated — open detail for full text.</p>
              )}
              <Link to={`/evidence/${item.id}`} className="aq-link inline-block mt-3 text-sm">
                View evidence
              </Link>
            </article>
          );
        })}
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
