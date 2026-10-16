import { useCallback, useEffect, useState } from "react";
import { loadSession } from "../../lib/api";
import { resolveApiBase } from "../../lib/apiBase";

type FleetRow = {
  name: string;
  url: string;
  version?: string | null;
  status: string;
  degraded?: string[];
  dependencies?: Record<string, string | undefined>;
  license?: string | null;
  checked_at: string;
  last_ok_at?: string | null;
  error?: string;
};

type FleetResponse = {
  configured: number;
  environments: FleetRow[];
  this_environment: { version: string; deployment_mode: string };
};

/** Dedicated client environments (FLEET_ENVIRONMENTS): version + last health check. */
export default function SuperAdminFleetPage() {
  const [data, setData] = useState<FleetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    const session = loadSession();
    if (!session?.token) return;
    setLoading(true);
    fetch(`${resolveApiBase()}/api/v1/admin/system/fleet`, { headers: { Authorization: `Bearer ${session.token}` } })
      .then(async (res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json() as Promise<FleetResponse>;
      })
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch(() => setError("Could not load fleet status."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main className="admin-main-canvas p-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold">Dedicated environments</h2>
        <button type="button" className="aq-btn" onClick={load} disabled={loading}>
          {loading ? "Checking…" : "Check now"}
        </button>
      </div>
      <p className="text-sm text-chat-muted mb-4">
        Version and health reported by each environment&apos;s public /api/v1/version and /health (metadata only).
        {data ? ` This console runs ${data.this_environment.version}.` : ""}
      </p>
      {error ? <p className="text-sm text-[var(--color-danger)]">{error}</p> : null}
      {data && data.configured === 0 ? (
        <p className="text-sm text-chat-muted">No environments configured. Set FLEET_ENVIRONMENTS=name=https://url,…</p>
      ) : null}
      {data && data.environments.length > 0 ? (
        <table className="w-full text-sm admin-card overflow-hidden">
          <thead className="bg-chat-surface-subtle text-left text-xs text-chat-muted">
            <tr>
              <th className="p-3">Client</th>
              <th className="p-3">Version</th>
              <th className="p-3">Health</th>
              <th className="p-3">Dependencies</th>
              <th className="p-3">License</th>
              <th className="p-3">Last check</th>
              <th className="p-3">Last OK</th>
            </tr>
          </thead>
          <tbody>
            {data.environments.map((r) => (
              <tr key={r.url} className="border-t border-chat-border">
                <td className="p-3">
                  <a className="text-[var(--color-link)] underline" href={r.url} target="_blank" rel="noreferrer">
                    {r.name}
                  </a>
                </td>
                <td className="p-3 font-mono">{r.version ?? "—"}</td>
                <td className="p-3 capitalize">
                  {r.status}
                  {r.error ? ` (${r.error})` : ""}
                </td>
                <td className="p-3 text-xs">
                  {r.dependencies
                    ? Object.entries(r.dependencies)
                        .map(([k, v]) => `${k}: ${v ?? "?"}`)
                        .join(", ")
                    : "—"}
                </td>
                <td className="p-3">{r.license ?? "—"}</td>
                <td className="p-3 text-xs">{r.checked_at}</td>
                <td className="p-3 text-xs">{r.last_ok_at ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </main>
  );
}
