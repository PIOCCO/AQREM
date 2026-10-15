import { useEffect, useState } from "react";
import { loadSession } from "../../lib/api";
import { resolveApiBase } from "../../lib/apiBase";

type EnvRow = {
  organization_id: string;
  organization_name: string;
  environment_id: string;
  deployment_status: string;
  deployment_region: string | null;
  health_status: string | null;
  application_version: string | null;
  license_status: string;
};

export default function SuperAdminDeploymentsPage() {
  const [rows, setRows] = useState<EnvRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token) return;
    fetch(`${resolveApiBase()}/api/v1/master/environments`, {
      headers: { Authorization: `Bearer ${session.token}` },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Failed to load deployments");
        return res.json() as Promise<EnvRow[]>;
      })
      .then(setRows)
      .catch(() => setError("Could not load deployment metadata."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="admin-main-canvas p-6">
      <h2 className="text-lg font-semibold mb-2">Deployments</h2>
      <p className="text-sm text-chat-muted mb-4">Organization environment metadata only — not tenant file content.</p>
      {loading ? <p className="text-sm text-chat-muted">Loading…</p> : null}
      {error ? <p className="text-sm text-[var(--color-danger)]">{error}</p> : null}
      {!loading && !error && rows.length === 0 ? (
        <p className="text-sm text-chat-muted">No deployment records yet.</p>
      ) : null}
      {rows.length > 0 ? (
        <table className="w-full text-sm admin-card overflow-hidden">
          <thead className="bg-chat-surface-subtle text-left text-xs text-chat-muted">
            <tr>
              <th className="p-3">Organization</th>
              <th className="p-3">Status</th>
              <th className="p-3">Region</th>
              <th className="p-3">Health</th>
              <th className="p-3">Version</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.environment_id} className="border-t border-chat-border">
                <td className="p-3">{r.organization_name}</td>
                <td className="p-3 capitalize">{r.deployment_status}</td>
                <td className="p-3">{r.deployment_region ?? "—"}</td>
                <td className="p-3 capitalize">{r.health_status ?? "—"}</td>
                <td className="p-3">{r.application_version ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </main>
  );
}
