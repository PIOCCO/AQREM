import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "../lib/authContext";
import { fetchModelToken, saveModelToken, testModelToken, type ModelTokenInfo } from "../lib/orgAdminApi";

export default function ClientAdminModelTokenPage() {
  const { session } = useAuth();
  const [info, setInfo] = useState<ModelTokenInfo | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!session) return;
    fetchModelToken(session)
      .then(setInfo)
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
      .finally(() => setLoading(false));
  }, [session]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!session) return;
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const next = await saveModelToken(session, tokenInput);
      setInfo(next);
      setTokenInput("");
      setSuccess("Token saved to your Key Vault. It will not be shown again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function onTest() {
    if (!session) return;
    setError(null);
    try {
      const res = await testModelToken(session);
      setSuccess(res.message);
      const next = await fetchModelToken(session);
      setInfo(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    }
  }

  if (loading) return <p className="p-8 text-sm text-chat-muted">Loading model token…</p>;

  return (
    <div className="max-w-2xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-semibold tracking-tight">Model token</h1>
      <p className="text-sm text-chat-muted mt-2">
        Enter your Azure OpenAI key once. It is stored in your organization&apos;s Key Vault, not in the platform
        database.
      </p>

      {info?.expiry_warning_days != null && info.expiry_warning_days <= 30 ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mt-4 text-sm" role="alert">
          Token expires in {info.expiry_warning_days} days. Plan a rotation before employees lose access.
        </div>
      ) : null}

      <div className="admin-card p-6 mt-6 space-y-3 text-sm">
        <div>
          <span className="text-chat-muted">Status</span>
          <p className="font-medium capitalize">{info?.status.replace(/_/g, " ")}</p>
        </div>
        <div>
          <span className="text-chat-muted">Masked value</span>
          <p className="font-mono">{info?.masked_value}</p>
        </div>
        {info?.last_rotated_at ? (
          <div>
            <span className="text-chat-muted">Last rotated</span>
            <p>{new Date(info.last_rotated_at).toLocaleString()}</p>
          </div>
        ) : null}
        {info?.last_test_at ? (
          <div>
            <span className="text-chat-muted">Last connection test</span>
            <p>
              {info.last_test_status} · {new Date(info.last_test_at).toLocaleString()}
            </p>
          </div>
        ) : null}
      </div>

      <form className="admin-card p-6 mt-6 space-y-4" onSubmit={onSubmit}>
        <div>
          <label htmlFor="model-token" className="block text-sm font-medium mb-1">
            New model token
          </label>
          <input
            id="model-token"
            name="token"
            type="password"
            autoComplete="off"
            className="admin-input w-full"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            minLength={8}
            required={info?.status === "not_configured"}
          />
          <p className="text-xs text-chat-muted mt-1">Minimum 8 characters. Never share this value in chat or email.</p>
        </div>
        {error ? (
          <div className="admin-inline-alert border rounded px-3 py-2 text-sm" role="alert">
            {error}
          </div>
        ) : null}
        {success ? (
          <div className="text-sm text-[var(--admin-status-active-text)] bg-[var(--admin-status-active-bg)] rounded px-3 py-2" role="status">
            {success}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <button type="submit" className="aq-btn-primary" disabled={saving || !tokenInput}>
            {saving ? "Saving…" : "Save to Key Vault"}
          </button>
          <button type="button" className="aq-btn-secondary" onClick={() => void onTest()} disabled={info?.status === "not_configured"}>
            Test connection
          </button>
        </div>
      </form>
    </div>
  );
}
