import { useEffect, useState } from "react";
import { useAuth } from "../lib/authContext";
import { fetchOrgUsage } from "../lib/orgAdminApi";

export default function ClientAdminUsagePage() {
  const { session } = useAuth();
  const [data, setData] = useState<{ active_users: number; storage_bytes: number; indexed_documents: number; queries_last_30_days: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    fetchOrgUsage(session)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"));
  }, [session]);

  if (error) {
    return (
      <div className="p-8 admin-inline-alert border rounded m-6" role="alert">
        {error}
      </div>
    );
  }
  if (!data) return <p className="p-8 text-sm text-chat-muted">Loading usage…</p>;

  return (
    <div className="max-w-4xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-semibold tracking-tight">Usage</h1>
      <p className="text-sm text-chat-muted mt-2">Operational metrics for your private assistant (no question text is stored here).</p>
      <div className="grid sm:grid-cols-3 gap-4 mt-8">
        <div className="admin-card p-4">
          <p className="text-xs text-chat-muted">Active users</p>
          <p className="text-2xl font-semibold mt-1">{data.active_users}</p>
        </div>
        <div className="admin-card p-4">
          <p className="text-xs text-chat-muted">Storage used</p>
          <p className="text-2xl font-semibold mt-1">{(data.storage_bytes / (1024 * 1024)).toFixed(2)} MB</p>
        </div>
        <div className="admin-card p-4">
          <p className="text-xs text-chat-muted">Indexed documents</p>
          <p className="text-2xl font-semibold mt-1">{data.indexed_documents}</p>
        </div>
      </div>
    </div>
  );
}
