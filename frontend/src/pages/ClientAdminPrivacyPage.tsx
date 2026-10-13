import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/authContext";
import { fetchChatSharing, fetchTelemetrySchema, updateChatSharing } from "../lib/orgAdminApi";

export default function ClientAdminPrivacyPage() {
  const { session } = useAuth();
  const [schema, setSchema] = useState<{ title: string; description: string; fields: Array<{ field: string; description: string }> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sharingEnabled, setSharingEnabled] = useState(false);
  const [sharingBusy, setSharingBusy] = useState(false);

  useEffect(() => {
    if (!session) return;
    fetchTelemetrySchema(session)
      .then(setSchema)
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"));
    fetchChatSharing(session)
      .then((s) => setSharingEnabled(s.enabled))
      .catch(() => undefined);
  }, [session]);

  async function toggleSharing() {
    if (!session) return;
    setSharingBusy(true);
    setError(null);
    try {
      const next = await updateChatSharing(session, { enabled: !sharingEnabled });
      setSharingEnabled(next.enabled);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update sharing");
    } finally {
      setSharingBusy(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-semibold tracking-tight">Privacy</h1>
      <section className="admin-card p-6 mt-6 space-y-3 text-sm">
        <h2 className="font-medium">Conversation sharing</h2>
        <p className="text-chat-muted">
          Sharing is off by default. When enabled, employees can create read-only links that expire automatically.
        </p>
        <button type="button" className="admin-btn-secondary" disabled={sharingBusy} onClick={() => void toggleSharing()}>
          {sharingEnabled ? "Disable share links" : "Enable share links"}
        </button>
      </section>
      <section className="admin-card p-6 mt-6 space-y-3 text-sm">
        <h2 className="font-medium">Your data stays in your environment</h2>
        <ul className="list-disc pl-5 text-chat-muted space-y-2">
          <li>Documents and embeddings remain inside your organization&apos;s storage and database.</li>
          <li>Model tokens are stored in your Key Vault — Azelos never keeps the secret in the platform database.</li>
          <li>Employee questions and answers are not sent to the master console.</li>
        </ul>
      </section>
      <section className="admin-card p-6 mt-6">
        <h2 className="font-medium text-sm">{schema?.title ?? "What Azelos can see"}</h2>
        <p className="text-sm text-chat-muted mt-2">{schema?.description}</p>
        {error ? (
          <p className="admin-inline-alert border rounded px-3 py-2 mt-4 text-sm" role="alert">
            {error}
          </p>
        ) : null}
        {schema?.fields ? (
          <ul className="mt-4 space-y-2 text-sm">
            {schema.fields.map((f) => (
              <li key={f.field}>
                <code className="text-xs bg-chat-surface-subtle px-1 rounded">{f.field}</code>
                <span className="text-chat-muted ml-2">{f.description}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-chat-muted mt-4">Loading telemetry field list…</p>
        )}
        <Link to="/admin" className="text-sm text-[var(--chat-brand-mark)] inline-block mt-4">
          ← Back to setup
        </Link>
      </section>
    </div>
  );
}
