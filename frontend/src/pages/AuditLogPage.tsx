import { useEffect, useMemo, useState } from "react";
import WorkspacePage from "../components/layout/WorkspacePage";
import { CopyButton } from "../components/ui/CopyButton";
import { EmptyState, ErrorState, LoadingState, PageLead } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
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

function toCsv(rows: AuditItem[]): string {
  const header = "id,action,resource_type,resource_id,created_at";
  const lines = rows.map((r) =>
    [r.id, r.action, r.resource_type, r.resource_id ?? "", r.created_at]
      .map((c) => `"${String(c).replace(/"/g, '""')}"`)
      .join(","),
  );
  return [header, ...lines].join("\n");
}

export default function AuditLogPage() {
  const { session } = useProjectContext();
  const toast = useToast();
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
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

  const filtered = useMemo(() => {
    let rows = [...items];
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (r) =>
          r.action.toLowerCase().includes(q) ||
          r.resource_type.toLowerCase().includes(q) ||
          (r.resource_id ?? "").toLowerCase().includes(q),
      );
    }
    if (dateFrom) {
      const from = new Date(dateFrom).getTime();
      rows = rows.filter((r) => new Date(r.created_at).getTime() >= from);
    }
    if (dateTo) {
      const to = new Date(dateTo).getTime() + 86400000;
      rows = rows.filter((r) => new Date(r.created_at).getTime() <= to);
    }
    rows.sort((a, b) => {
      const da = new Date(a.created_at).getTime();
      const db = new Date(b.created_at).getTime();
      return sort === "newest" ? db - da : da - db;
    });
    return rows;
  }, [items, search, dateFrom, dateTo, sort]);

  function exportCsv() {
    const blob = new Blob([toCsv(filtered)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "activity-export.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.push(`Exported ${filtered.length} events to CSV`);
  }

  return (
    <WorkspacePage>
      <PageLead subtitle={`${total} organization events (secrets are never logged).`} />
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          className="aq-input max-w-xs"
          placeholder="Search activity…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search activity"
        />
        <input
          className="aq-input max-w-xs"
          placeholder="Filter action (exact)…"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value.trim())}
          aria-label="Filter by action"
        />
        <select className="aq-input max-w-[10rem]" value={sort} onChange={(e) => setSort(e.target.value as "newest" | "oldest")} aria-label="Sort">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
        <input type="date" className="aq-input" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} aria-label="From date" />
        <input type="date" className="aq-input" value={dateTo} onChange={(e) => setDateTo(e.target.value)} aria-label="To date" />
        <button type="button" className="aq-btn-secondary" onClick={exportCsv} disabled={filtered.length === 0}>
          Export CSV
        </button>
      </div>
      {loading && <LoadingState label="Loading activity…" />}
      {error && <ErrorState message={error} onRetry={() => load(false, 0)} />}
      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title="No activity yet"
          description="Actions such as approvals, exports, and indexing will appear here."
        />
      )}
      <ul className="space-y-2">
        {filtered.map((item) => {
          const open = expandedId === item.id;
          return (
            <li key={item.id}>
              <button
                type="button"
                className="aq-card w-full px-4 py-3 text-sm text-left aq-interactive-row"
                onClick={() => setExpandedId(open ? null : item.id)}
                aria-expanded={open}
              >
                <div className="flex flex-wrap justify-between gap-2 items-center">
                  <span className="font-medium capitalize text-[var(--color-text-primary)] flex items-center gap-2">
                    {item.action.replaceAll("_", " ")}
                    <span className="text-[var(--color-text-muted)] text-xs">{open ? "▾" : "▸"}</span>
                  </span>
                  <time className="text-xs text-[var(--color-text-muted)]" dateTime={item.created_at}>
                    {new Date(item.created_at).toLocaleString()}
                  </time>
                </div>
                <p className="text-xs text-[var(--color-text-secondary)] mt-1 font-mono truncate">
                  {item.resource_type}
                  {item.resource_id ? ` · ${item.resource_id.slice(0, 8)}…` : ""}
                </p>
                {open ? (
                  <div className="mt-3 pt-3 border-t border-border space-y-2" onClick={(e) => e.stopPropagation()}>
                    <p className="text-xs font-mono break-all text-[var(--color-text-secondary)]">{item.resource_id ?? "—"}</p>
                    <div className="flex gap-2">
                      <CopyButton value={item.id} label="Copy event ID" />
                      {item.resource_id ? <CopyButton value={item.resource_id} label="Copy resource ID" /> : null}
                    </div>
                  </div>
                ) : null}
              </button>
            </li>
          );
        })}
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
