import { useEffect, useState } from "react";
import { useAuth } from "../lib/authContext";
import { fetchOrgAudit } from "../lib/orgAdminApi";

export default function ClientAdminAuditPage() {
  const { session } = useAuth();
  const [rows, setRows] = useState<Array<{ id: string; created_at: string; action: string; resource_type: string; actor_email: string | null }>>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    fetchOrgAudit(session)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"));
  }, [session]);

  if (error) {
    return (
      <div className="p-8 admin-inline-alert border rounded m-6" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-semibold tracking-tight">Security & audit</h1>
      <p className="text-sm text-chat-muted mt-2">Administrative actions in your organization (no document content).</p>
      {rows.length === 0 ? (
        <p className="admin-card p-6 mt-6 text-sm text-chat-muted">No audit events yet.</p>
      ) : (
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
      )}
    </div>
  );
}
