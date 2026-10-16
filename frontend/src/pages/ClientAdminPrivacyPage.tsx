import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/authContext";
import {
  fetchChatGuardrails,
  fetchChatSharing,
  fetchTelemetrySchema,
  updateChatGuardrails,
  updateChatSharing,
  type ChatStrictness,
} from "../lib/orgAdminApi";

export default function ClientAdminPrivacyPage() {
  const { session } = useAuth();
  const [schema, setSchema] = useState<{ title: string; description: string; fields: Array<{ field: string; description: string }> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sharingEnabled, setSharingEnabled] = useState(false);
  const [sharingBusy, setSharingBusy] = useState(false);
  const [strictness, setStrictness] = useState<ChatStrictness>("balanced");
  const [strictBusy, setStrictBusy] = useState(false);

  useEffect(() => {
    if (!session) return;
    fetchTelemetrySchema(session)
      .then(setSchema)
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"));
    fetchChatSharing(session)
      .then((s) => setSharingEnabled(s.enabled))
      .catch(() => undefined);
    fetchChatGuardrails(session)
      .then((g) => setStrictness(g.strictness))
      .catch(() => undefined);
  }, [session]);

  async function changeStrictness(next: ChatStrictness) {
    if (!session || next === strictness) return;
    setStrictBusy(true);
    setError(null);
    try {
      const saved = await updateChatGuardrails(session, { strictness: next });
      setStrictness(saved.strictness);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update guardrails");
    } finally {
      setStrictBusy(false);
    }
  }

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
        <h2 className="font-medium">Assistant answer strictness</h2>
        <p className="text-chat-muted">
          The assistant only answers from your documents and refuses off-topic requests in both modes.
          Strict requires stronger document matches and skips small talk; balanced allows greetings and
          looser matching for summary requests.
        </p>
        <div className="flex gap-4" role="radiogroup" aria-label="Assistant strictness">
          {(["balanced", "strict"] as ChatStrictness[]).map((level) => (
            <label key={level} className="flex items-center gap-2">
              <input
                type="radio"
                name="chat-strictness"
                value={level}
                checked={strictness === level}
                disabled={strictBusy}
                onChange={() => void changeStrictness(level)}
              />
              {level === "strict" ? "Strict" : "Balanced"}
            </label>
          ))}
        </div>
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
