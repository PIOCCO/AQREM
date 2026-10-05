import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchAuditLog } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

type AuditItem = {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  created_at: string;
};

export default function AuditLogPage() {
  const { session } = useProjectContext();
  const [items, setItems] = useState<AuditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!session) return;
    setLoading(true);
    try {
      const data = await fetchAuditLog(session);
      setItems(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load activity");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [session?.organizationId]);

  return (
    <div>
      <PageHeader title="Audit Log" subtitle="Recent organization events (secrets are never logged)." />
      {loading && <LoadingState label="Loading activity…" />}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState title="No activity yet" description="Actions such as approvals, exports, and indexing will appear here." />
      )}
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="aq-card px-4 py-3 text-sm">
            <div className="flex flex-wrap justify-between gap-2">
              <span className="font-medium capitalize text-slate-900">{item.action.replaceAll("_", " ")}</span>
              <time className="text-xs text-slate-500" dateTime={item.created_at}>
                {new Date(item.created_at).toLocaleString()}
              </time>
            </div>
            <p className="text-xs text-slate-600 mt-1 font-mono">
              {item.resource_type}
              {item.resource_id ? ` · ${item.resource_id.slice(0, 8)}…` : ""}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
