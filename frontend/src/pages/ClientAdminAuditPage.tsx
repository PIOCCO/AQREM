import { useCallback, useEffect, useState } from "react";
import { CleanUpAuditDialog, type AuditCleanupScope } from "../components/admin/CleanUpAuditDialog";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../lib/authContext";
import {
  cleanupOrgAuditLogs,
  downloadOrgAuditCsv,
  fetchOrgAudit,
  type OrgAuditRow,
} from "../lib/orgAdminApi";

function TrashIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M3 6h18M8 6V4h8v2m-1 4v8H9v-8m-3-4h12l-1 14H7L6 6z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ClientAdminAuditPage() {
  const { session } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState<OrgAuditRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 50;
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [cleanupOpen, setCleanupOpen] = useState(false);
  const [cleanupBusy, setCleanupBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOrgAudit(session, page, pageSize);
      setRows(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [session, page]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCleanup(scope: AuditCleanupScope) {
    if (!session) return;
    setCleanupBusy(true);
    try {
      const result = await cleanupOrgAuditLogs(session, scope);
      setCleanupOpen(false);
      toast.push(`${result.deleted_count} log entries deleted`, "ok");
      setPage(1);
      await load();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Cleanup failed", "err");
    } finally {
      setCleanupBusy(false);
    }
  }

  async function onExport() {
    if (!session) return;
    setExportBusy(true);
    try {
      await downloadOrgAuditCsv(session);
      toast.push("Audit log downloaded", "ok");
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Export failed", "err");
    } finally {
      setExportBusy(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (error && rows.length === 0 && !loading) {
    return (
      <div className="p-8 admin-inline-alert border rounded m-6" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6 lg:p-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Security & audit</h1>
          <p className="text-sm text-chat-muted mt-2">Administrative actions in your organization (no document content).</p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <button
            type="button"
            className="admin-btn-secondary min-h-10"
            disabled={exportBusy || loading}
            onClick={() => void onExport()}
          >
            {exportBusy ? "Exporting…" : "Download CSV"}
          </button>
          <button
            type="button"
            className="admin-btn-danger-outline inline-flex items-center gap-2 min-h-10"
            disabled={loading || cleanupBusy}
            onClick={() => setCleanupOpen(true)}
          >
            <TrashIcon />
            {cleanupBusy ? "Cleaning…" : "Clean up logs"}
          </button>
        </div>
      </div>

      {loading && rows.length === 0 ? (
        <p className="admin-card p-6 mt-6 text-sm text-chat-muted">Loading audit log…</p>
      ) : rows.length === 0 ? (
        <p className="admin-card p-6 mt-6 text-sm text-chat-muted">No audit logs</p>
      ) : (
        <>
          <div className="admin-card overflow-x-auto mt-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-chat-muted border-b border-chat-border">
                  <th className="p-3">When</th>
                  <th className="p-3">Who</th>
                  <th className="p-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-chat-border last:border-0">
                    <td className="p-3 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                    <td className="p-3">{r.actor_email ?? "System"}</td>
                    <td className="p-3">
                      {r.action} · {r.resource_type}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 ? (
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-chat-muted">
                Page {page} of {totalPages} ({total} entries)
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="admin-btn-secondary text-xs min-h-8"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="admin-btn-secondary text-xs min-h-8"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
        </>
      )}

      <CleanUpAuditDialog
        open={cleanupOpen}
        loading={cleanupBusy}
        onCancel={() => setCleanupOpen(false)}
        onConfirm={(scope) => void onCleanup(scope)}
      />
    </div>
  );
}
