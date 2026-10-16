import { useCallback, useEffect, useState } from "react";
import type { AuthSession } from "../../lib/api";
import {
  fetchAiStatus,
  reindexAllDocuments,
  testAiConnection,
  type AiConnectionTest,
  type AiStatus,
} from "../../lib/orgAdminApi";

/** Active AI provider, "Test AI connection" and "Re-index all documents" (org admin). */
export default function AiProviderPanel({ session, onReindexed }: { session: AuthSession; onReindexed?: () => void }) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [test, setTest] = useState<AiConnectionTest | null>(null);
  const [busy, setBusy] = useState<"test" | "reindex" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchAiStatus(session)
      .then(setStatus)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load AI status"));
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  async function runTest() {
    setBusy("test");
    setError(null);
    setTest(null);
    try {
      setTest(await testAiConnection(session));
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI connection test failed");
    } finally {
      setBusy(null);
    }
  }

  async function runReindex() {
    if (!window.confirm("Re-index all documents with the current embedding deployment? Search quality may drop until it finishes.")) return;
    setBusy("reindex");
    setError(null);
    try {
      const r = await reindexAllDocuments(session);
      setMessage(`Queued ${r.queued} document(s) for re-indexing${r.skipped_in_progress ? ` (${r.skipped_in_progress} already in progress)` : ""}.`);
      onReindexed?.();
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Re-index failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="admin-card p-4 mb-6 text-sm" aria-label="AI provider">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-medium">AI provider: {status ? status.provider : "…"}</div>
          {status ? (
            <div className="text-chat-muted mt-1">
              {status.chat_deployment ? `Chat deployment: ${status.chat_deployment} · ` : ""}
              {status.embedding_deployment ? `Embedding deployment: ${status.embedding_deployment} · ` : ""}
              Vector size: {status.dimensions}
            </div>
          ) : null}
        </div>
        <div className="flex gap-2">
          <button type="button" className="admin-btn-secondary px-3 py-1.5 rounded-md border" disabled={busy !== null} onClick={() => void runTest()}>
            {busy === "test" ? "Testing…" : "Test AI connection"}
          </button>
          <button type="button" className="admin-btn-secondary px-3 py-1.5 rounded-md border" disabled={busy !== null} onClick={() => void runReindex()}>
            {busy === "reindex" ? "Queuing…" : "Re-index all documents"}
          </button>
        </div>
      </div>
      {status?.embedding_warning ? (
        <div className="admin-inline-alert border rounded-lg px-3 py-2 mt-3 text-amber-200" role="alert">
          {status.embedding_warning}
        </div>
      ) : null}
      {test ? (
        <ul className="mt-3 space-y-1" role="status">
          {test.error ? <li className="text-red-500">{test.error}</li> : null}
          {test.chat ? (
            <li className={test.chat.ok ? "text-green-500" : "text-red-500"}>
              Chat: {test.chat.ok ? "OK" : "Failed"} — {test.chat.message}
            </li>
          ) : null}
          {test.embeddings ? (
            <li className={test.embeddings.ok ? "text-green-500" : "text-red-500"}>
              Embeddings: {test.embeddings.ok ? "OK" : "Failed"} — {test.embeddings.message}
            </li>
          ) : null}
        </ul>
      ) : null}
      {message ? <p className="mt-2 text-chat-muted">{message}</p> : null}
      {error ? <p className="mt-2 text-red-500">{error}</p> : null}
    </section>
  );
}
