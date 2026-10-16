import { useState } from "react";
import { loadSession } from "../lib/api";
import { resolveApiBase } from "../lib/apiBase";

type Check = { name: string; status: string; message: string };
type DbReport = { target: string; role: string; ok: boolean; checks: Check[] };

/**
 * "Test database" + "Download diagnostics" for operators.
 * scope=platform -> /api/v1/admin/system (super admin); scope=org -> /api/v1/org-admin/system (dedicated only).
 */
export default function SystemToolsCard({ scope }: { scope: "platform" | "org" }) {
  const base = `${resolveApiBase()}/api/v1/${scope === "platform" ? "admin" : "org-admin"}/system`;
  const [reports, setReports] = useState<Record<string, DbReport> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function headers(): HeadersInit {
    const s = loadSession();
    const h: Record<string, string> = { Authorization: `Bearer ${s?.token ?? ""}` };
    if (scope === "org" && s?.organizationId) h["X-Organization-Id"] = s.organizationId;
    return h;
  }

  async function testDb() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${base}/database-check`, { headers: headers() });
      if (!res.ok) throw new Error(String(res.status));
      setReports((await res.json()) as Record<string, DbReport>);
    } catch {
      setError("Database check is not available.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadDiagnostics() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${base}/diagnostics`, { headers: headers() });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aqrem-diagnostics-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not download diagnostics.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="admin-card p-4 mt-4" aria-labelledby="system-tools-title">
      <h3 id="system-tools-title" className="font-semibold mb-1">
        System checks
      </h3>
      <p className="text-sm text-chat-muted mb-3">
        Diagnostics contain versions, dependency status and error summaries — no secrets or document content.
      </p>
      <div className="flex gap-2 flex-wrap">
        <button type="button" className="aq-btn" onClick={testDb} disabled={busy}>
          Test database
        </button>
        <button type="button" className="aq-btn" onClick={downloadDiagnostics} disabled={busy}>
          Download diagnostics
        </button>
      </div>
      {error ? <p className="text-sm text-[var(--color-danger)] mt-2">{error}</p> : null}
      {reports
        ? Object.entries(reports).map(([key, r]) => (
            <div key={key} className="mt-3">
              <p className="text-sm font-medium">
                {key === "app" ? "Application role" : "Migration role"} — {r.target}: {r.ok ? "OK" : "problems found"}
              </p>
              <ul className="text-sm mt-1 space-y-1">
                {r.checks.map((c) => (
                  <li key={c.name}>
                    <span className="font-mono uppercase text-xs mr-2">{c.status}</span>
                    <span className="font-medium">{c.name}</span>: {c.message}
                  </li>
                ))}
              </ul>
            </div>
          ))
        : null}
    </section>
  );
}
