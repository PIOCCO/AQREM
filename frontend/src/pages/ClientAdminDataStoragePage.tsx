import { FormEvent, useCallback, useEffect, useId, useState } from "react";
import { useAuth } from "../lib/authContext";
import {
  configureDataStorage,
  fetchDataStorage,
  runDataStoragePreflight,
  type DataStorageConfig,
  type PreflightReport,
} from "../lib/orgAdminApi";

type LocationChoice = "managed" | "customer";

const CONNECTION_METHODS = [
  { value: "public_tls", label: "Public endpoint with TLS (IP allow-list)" },
  { value: "private_link", label: "Private link / VNet peering / VPN" },
  { value: "secure_connector", label: "Secure connector (on-premises, outbound only)" },
  { value: "customer_deployed", label: "Deploy in my environment" },
] as const;

export default function ClientAdminDataStoragePage() {
  const { session } = useAuth();
  const formId = useId();
  const [status, setStatus] = useState<DataStorageConfig | null>(null);
  const [location, setLocation] = useState<LocationChoice | null>(null);
  const [connectionMethod, setConnectionMethod] = useState("public_tls");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("5432");
  const [databaseName, setDatabaseName] = useState("");
  const [schemaName, setSchemaName] = useState("public");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [sslMode, setSslMode] = useState("verify-full");
  const [preflight, setPreflight] = useState<PreflightReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!session) return;
    setError(null);
    try {
      const cfg = await fetchDataStorage(session);
      setStatus(cfg);
      if (cfg.setup_complete) {
        setLocation(cfg.storage_mode === "customer_postgres" ? "customer" : "managed");
      }
      setConnectionMethod(cfg.connection_method || "public_tls");
      setHost(cfg.host ?? "");
      setPort(String(cfg.port ?? 5432));
      setDatabaseName(cfg.database_name ?? "");
      setSchemaName(cfg.schema_name || "public");
      setUsername(cfg.username ?? "");
      setSslMode(cfg.ssl_mode || "verify-full");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load storage settings");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onPreflight(e: FormEvent) {
    e.preventDefault();
    if (!session) return;
    setError(null);
    setSuccess(null);
    setPreflight(null);
    setBusy(true);
    try {
      if (location === null) {
        setError("Select a database option before running validation.");
        return;
      }
      const report = await runDataStoragePreflight(session, {
        storage_mode: location === "managed" ? "managed_colocated" : "customer_postgres",
        connection_method: connectionMethod,
        host: host || null,
        port: port ? Number(port) : 5432,
        database_name: databaseName || null,
        schema_name: schemaName,
        ssl_mode: sslMode,
        username: username || null,
        password: password || null,
      });
      setPreflight(report);
      if (report.ok) setSuccess("Preflight passed. Save to apply migrations and activate this database.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preflight failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!session) return;
    if (location === null) {
      setError("Select AQREM-managed PostgreSQL or My PostgreSQL database before saving.");
      return;
    }
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const cfg = await configureDataStorage(session, {
        storage_mode: location === "managed" ? "managed_colocated" : "customer_postgres",
        connection_method: connectionMethod,
        host: host || null,
        port: port ? Number(port) : 5432,
        database_name: databaseName || null,
        schema_name: schemaName,
        ssl_mode: sslMode,
        username: username || null,
        password: password || null,
      });
      setStatus(cfg);
      setPassword("");
      setSuccess(
        location === "managed"
          ? "AQREM-managed PostgreSQL is active. The setup checklist will reflect this after you return to Overview."
          : "Your PostgreSQL connection is validated and active. Credentials are stored in the secret vault only.",
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="p-8 text-sm text-chat-muted">Loading data storage…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-semibold tracking-tight">PostgreSQL database</h1>
      <p className="text-sm text-chat-muted mt-2">
        Choose where your tenant data is stored. Select an option below and save after validation succeeds. Credentials
        are never returned to the browser.
      </p>

      {status && !status.setup_complete ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mt-4 text-sm" role="status">
          No database mode is active yet. Pick AQREM-managed PostgreSQL or connect your own database, then save.
        </div>
      ) : null}

      {status ? (
        <div className="admin-card p-6 mt-6 grid gap-3 text-sm sm:grid-cols-2" aria-live="polite">
          <div>
            <span className="text-chat-muted">Setup</span>
            <p className="font-medium">{status.setup_complete ? "Configured" : "Not configured"}</p>
          </div>
          <div>
            <span className="text-chat-muted">Active mode</span>
            <p className="font-medium">
              {status.setup_complete
                ? status.storage_mode === "managed_colocated"
                  ? "AQREM-managed PostgreSQL"
                  : "Your PostgreSQL"
                : "None selected"}
            </p>
          </div>
          <div>
            <span className="text-chat-muted">Schema version</span>
            <p>{status.schema_version}</p>
          </div>
          <div>
            <span className="text-chat-muted">Last health check</span>
            <p>
              {status.last_health_check_at
                ? `${status.last_health_status ?? "unknown"} · ${new Date(status.last_health_check_at).toLocaleString()}`
                : "Not yet checked"}
            </p>
          </div>
          {status.last_health_summary ? (
            <div className="sm:col-span-2">
              <span className="text-chat-muted">Summary</span>
              <p>{status.last_health_summary}</p>
            </div>
          ) : null}
        </div>
      ) : null}

      <form id={formId} className="admin-card p-6 mt-6 space-y-6" onSubmit={onSave}>
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">Database option</legend>
          <label className="flex gap-3 items-start cursor-pointer">
            <input
              type="radio"
              name="location"
              checked={location === "managed"}
              onChange={() => {
                setLocation("managed");
                setPreflight(null);
                setSuccess(null);
              }}
            />
            <span>
              <span className="font-medium block">AQREM-managed PostgreSQL</span>
              <span className="text-sm text-chat-muted">
                Use AQREM-managed PostgreSQL for your tenant data. AQREM operates the database infrastructure.
              </span>
            </span>
          </label>
          <label className="flex gap-3 items-start cursor-pointer">
            <input
              type="radio"
              name="location"
              checked={location === "customer"}
              onChange={() => {
                setLocation("customer");
                setPreflight(null);
                setSuccess(null);
              }}
            />
            <span>
              <span className="font-medium block">My PostgreSQL database</span>
              <span className="text-sm text-chat-muted">Connect your own PostgreSQL database with TLS.</span>
            </span>
          </label>
        </fieldset>

        {location === "customer" ? (
          <>
            <div>
              <label htmlFor="connection-method" className="block text-sm font-medium mb-1">
                Connection method
              </label>
              <select
                id="connection-method"
                className="admin-input w-full"
                value={connectionMethod}
                onChange={(e) => setConnectionMethod(e.target.value)}
              >
                {CONNECTION_METHODS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="db-host" className="block text-sm font-medium mb-1">
                  Host
                </label>
                <input
                  id="db-host"
                  className="admin-input w-full"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  autoComplete="off"
                  required
                />
              </div>
              <div>
                <label htmlFor="db-port" className="block text-sm font-medium mb-1">
                  Port
                </label>
                <input
                  id="db-port"
                  className="admin-input w-full"
                  inputMode="numeric"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                  required
                />
              </div>
              <div>
                <label htmlFor="db-name" className="block text-sm font-medium mb-1">
                  Database name
                </label>
                <input
                  id="db-name"
                  className="admin-input w-full"
                  value={databaseName}
                  onChange={(e) => setDatabaseName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label htmlFor="db-schema" className="block text-sm font-medium mb-1">
                  Schema
                </label>
                <input
                  id="db-schema"
                  className="admin-input w-full"
                  value={schemaName}
                  onChange={(e) => setSchemaName(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="db-user" className="block text-sm font-medium mb-1">
                  Username
                </label>
                <input
                  id="db-user"
                  className="admin-input w-full"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                  required
                />
              </div>
              <div>
                <label htmlFor="db-ssl" className="block text-sm font-medium mb-1">
                  SSL mode
                </label>
                <select id="db-ssl" className="admin-input w-full" value={sslMode} onChange={(e) => setSslMode(e.target.value)}>
                  <option value="verify-full">verify-full (recommended)</option>
                  <option value="require">require</option>
                </select>
              </div>
            </div>
            <div>
              <label htmlFor="db-password" className="block text-sm font-medium mb-1">
                Password
              </label>
              <input
                id="db-password"
                type="password"
                className="admin-input w-full"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                placeholder={status?.has_credentials ? "Leave blank to keep existing credentials" : "Required on first setup"}
              />
              <p className="text-xs text-chat-muted mt-1">
                Never shown again after save. Run the DBA setup script in{" "}
                <code className="text-xs">docs/sql/tenant_database_setup.sql</code> before connecting.
              </p>
            </div>
            <button
              type="button"
              className="admin-btn-secondary"
              disabled={busy}
              onClick={(ev) => void onPreflight(ev as unknown as FormEvent)}
            >
              Run preflight check
            </button>
            {preflight ? (
              <ul className="space-y-2 text-sm" aria-label="Preflight results">
                {preflight.checks.map((c) => (
                  <li
                    key={c.id}
                    className={`rounded px-3 py-2 border ${
                      c.status === "pass"
                        ? "border-[var(--admin-status-active-bg)]"
                        : c.status === "warn"
                          ? "border-amber-600/40"
                          : "border-red-500/40"
                    }`}
                  >
                    <span className="font-medium">{c.title}</span>
                    <span className="text-chat-muted"> — {c.status}</span>
                    <p className="mt-1 text-chat-muted">{c.detail}</p>
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-chat-muted">
              AQREM provisions and operates PostgreSQL for your organization. Saving runs a connectivity and schema check
              before activating this mode.
            </p>
            <button
              type="button"
              className="admin-btn-secondary"
              disabled={busy}
              onClick={(ev) => void onPreflight(ev as unknown as FormEvent)}
            >
              Test AQREM-managed connection
            </button>
            {preflight ? (
              <ul className="space-y-2 text-sm" aria-label="Managed validation results">
                {preflight.checks.map((c) => (
                  <li
                    key={c.id}
                    className={`rounded px-3 py-2 border ${
                      c.status === "pass" ? "border-[var(--admin-status-active-bg)]" : "border-red-500/40"
                    }`}
                  >
                    <span className="font-medium">{c.title}</span>
                    <span className="text-chat-muted"> — {c.status}</span>
                    <p className="mt-1 text-chat-muted">{c.detail}</p>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}

        {error ? (
          <div className="admin-inline-alert border rounded px-3 py-2 text-sm" role="alert">
            {error}
          </div>
        ) : null}
        {success ? (
          <div
            className="text-sm text-[var(--admin-status-active-text)] bg-[var(--admin-status-active-bg)] rounded px-3 py-2"
            role="status"
          >
            {success}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <button type="submit" className="admin-btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save and activate"}
          </button>
          <button type="button" className="admin-btn-secondary" disabled={busy} onClick={() => void load()}>
            Refresh status
          </button>
        </div>
      </form>
    </div>
  );
}
