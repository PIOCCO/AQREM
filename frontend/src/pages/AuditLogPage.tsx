import { useEffect, useState } from "react";
import WorkspacePage from "../components/layout/WorkspacePage";
import { EmptyState, ErrorState, LoadingState, PageLead } from "../components/ui/States";
import { fetchAuditLog } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

type AuditItem = {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  created_at: string;
};

const PAGE = 50;

export default function AuditLogPage() {
  const { session } = useProjectContext();
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(append = false, nextOffset = 0) {
    if (!session) return;
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const data = await fetchAuditLog(session, {
        offset: nextOffset,
        limit: PAGE,
        action: actionFilter || undefined,
      });
      setTotal(data.total);
      setOffset(nextOffset);
      setItems((prev) => (append ? [...prev, ...data.items] : data.items));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load activity");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    load(false, 0);
  }, [session?.organizationId, actionFilter]);

  return (
    <WorkspacePage>
      <PageLead subtitle={`${total} organization events (secrets are never logged).`} />
      <input
        className="aq-input max-w-md mb-4"
        placeholder="Filter by action (exact match)…"
        value={actionFilter}
        onChange={(e) => setActionFilter(e.target.value.trim())}
        aria-label="Filter activity by action"
      />
      {loading && <LoadingState label="Loading activity…" />}
      {error && <ErrorState message={error} onRetry={() => load(false, 0)} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState
          title="No activity yet"
          description="Actions such as approvals, exports, and indexing will appear here."
        />
      )}
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="aq-card px-4 py-3 text-sm">
            <div className="flex flex-wrap justify-between gap-2">
              <span className="font-medium capitalize text-[var(--color-text-primary)]">
                {item.action.replaceAll("_", " ")}
              </span>
              <time className="text-xs text-[var(--color-text-muted)]" dateTime={item.created_at}>
                {new Date(item.created_at).toLocaleString()}
              </time>
            </div>
            <p className="text-xs text-[var(--color-text-secondary)] mt-1 font-mono">
              {item.resource_type}
              {item.resource_id ? ` · ${item.resource_id.slice(0, 8)}…` : ""}
            </p>
          </li>
        ))}
      </ul>
      {items.length < total && !loading && (
        <button
          type="button"
          className="aq-btn-secondary mt-4"
          disabled={loadingMore}
          onClick={() => load(true, offset + PAGE)}
        >
          {loadingMore ? "Loading…" : `Load more (${items.length} of ${total})`}
        </button>
      )}
    </WorkspacePage>
  );
}
