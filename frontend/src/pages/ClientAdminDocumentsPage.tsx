import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/authContext";
import { fetchDocuments, removeDocument, retryDocument, uploadDocuments } from "../lib/orgAdminApi";

const ALLOWED_HINT = "PDF, Markdown, plain text, and .tar.gz archives";
const MAX_MB = 50;

type DocRow = {
  id: string;
  file_name: string;
  size_bytes: number;
  status: string;
  index_progress: number;
  index_stage: string;
  processed_units: number;
  total_units: number | null;
  indexed_chunk_count: number;
  index_started_at: string | null;
  index_finished_at: string | null;
  index_progress_updated_at: string | null;
  queue_ahead: number | null;
  failure_reason: string | null;
  visibility_mode: string;
  sensitivity_flag: boolean;
  acl_reviewed: boolean;
};

function visibilityLabel(mode: string) {
  switch (mode) {
    case "all_staff":
      return "All staff";
    case "admins_only":
      return "Admins only";
    default:
      return mode;
  }
}

function stageLabel(row: DocRow): string {
  const stage = row.index_stage || row.status;
  switch (stage) {
    case "queued":
      return row.queue_ahead != null && row.queue_ahead > 0
        ? `Waiting, ${row.queue_ahead} ahead`
        : "Queued";
    case "reading":
      return "Reading file";
    case "parsing":
      return "Parsing";
    case "chunking":
      return "Splitting";
    case "embedding":
      if (row.total_units != null && row.total_units > 0) {
        return `Embedding ${row.processed_units}/${row.total_units}`;
      }
      return "Embedding";
    case "writing":
      if (row.total_units != null && row.total_units > 0) {
        return `Saving ${row.processed_units}/${row.total_units}`;
      }
      return "Saving";
    case "indexed":
      return "Indexed";
    case "empty":
    case "failed":
      return "Failed";
    default:
      if (row.status === "indexing") return "Indexing";
      return row.status;
  }
}

function isActiveRow(row: DocRow): boolean {
  return ["queued", "uploading", "indexing"].includes(row.status) && !["indexed", "failed"].includes(row.index_stage);
}

function formatElapsed(startIso: string | null): string {
  if (!startIso) return "";
  const start = new Date(startIso).getTime();
  const sec = Math.max(0, Math.floor((Date.now() - start) / 1000));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function DocumentProgressCell({ row, tick }: { row: DocRow; tick: number }) {
  void tick;
  const active = isActiveRow(row);
  const showBar = active && row.total_units != null && row.total_units > 0;
  const label = stageLabel(row);
  return (
    <div className="space-y-1" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <span>{label}</span>
        {active && row.index_started_at ? (
          <span className="text-xs text-chat-muted">Indexing for {formatElapsed(row.index_started_at)}</span>
        ) : null}
        {row.index_stage === "indexed" && row.indexed_chunk_count > 0 ? (
          <span className="text-xs text-chat-muted">{row.indexed_chunk_count} chunks</span>
        ) : null}
      </div>
      {showBar ? (
        <div
          className="h-1.5 w-full max-w-[12rem] rounded-full bg-chat-surface-subtle overflow-hidden"
          role="progressbar"
          aria-valuenow={row.index_progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Indexing progress ${row.index_progress}%`}
        >
          <div className="h-full bg-[var(--chat-brand-mark)] transition-[width] duration-300" style={{ width: `${row.index_progress}%` }} />
        </div>
      ) : active && !showBar ? (
        <p className="text-xs text-chat-muted">{row.index_progress > 0 ? `${row.index_progress}%` : "Preparing…"}</p>
      ) : null}
    </div>
  );
}

export default function ClientAdminDocumentsPage() {
  const { session } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{
    items: DocRow[];
    total: number;
    counts: Record<string, number>;
    worker_reachable?: boolean;
    queue_wait_warning?: boolean;
  } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [visibilityMode, setVisibilityMode] = useState("admins_only");
  const [tick, setTick] = useState(0);

  const load = useCallback(
    (opts?: { silent?: boolean }) => {
      if (!session) return Promise.resolve();
      if (!opts?.silent) setLoading(true);
      return fetchDocuments(session, page, 10)
        .then((next) => {
          setData(next);
          setError(null);
        })
        .catch((e) => {
          if (!opts?.silent) {
            setError(e instanceof Error ? e.message : "Load failed");
          }
        })
        .finally(() => {
          if (!opts?.silent) setLoading(false);
        });
    },
    [session, page],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const indexingCount = data?.counts?.indexing ?? 0;

  useEffect(() => {
    if (!session || indexingCount <= 0) return;
    const id = window.setInterval(() => {
      void load({ silent: true });
    }, 1500);
    return () => window.clearInterval(id);
  }, [session, indexingCount, load]);

  useEffect(() => {
    if (indexingCount <= 0) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [indexingCount]);

  async function onFiles(files: FileList | null) {
    if (!session || !files?.length) return;
    setError(null);
    setUploading(true);
    try {
      await uploadDocuments(session, files, visibilityMode);
      await load({ silent: true }).catch(() => null);
    } catch (e) {
      const err = e as Error & { code?: string };
      const msg = err instanceof Error ? err.message : "Upload failed";
      const code = err.code;
      if (code === "DATABASE_NOT_CONFIGURED" || /PostgreSQL is not configured/i.test(msg)) {
        setError(
          "Data storage is not activated yet. Open Admin → Data storage, choose AQREM-managed PostgreSQL, and click Save and activate. Then try uploading again.",
        );
      } else if (code === "BROKER_UNAVAILABLE" || /broker|queue|worker|redis/i.test(msg)) {
        setError(
          "Indexing service is unavailable (503). Start Redis and the worker: docker compose -f docker-compose.local-prod.yml up -d redis worker worker-beat",
        );
      } else if (code === "STORAGE_UNAVAILABLE" || /storage|LOCAL_UPLOAD_DIR/i.test(msg)) {
        setError(msg);
      } else if (msg === "Failed to fetch") {
        setError(
          "Upload failed (network or CORS). Set PUBLIC_BASE_URL and CORS for your browser origin, and finish Data storage setup.",
        );
      } else {
        setError(msg);
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-6 lg:p-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="text-sm text-chat-muted mt-2">
          Upload private files for indexing. Allowed: {ALLOWED_HINT}. Max {MAX_MB} MB per file.
        </p>
      </header>

      {data?.worker_reachable === false ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mb-4 text-sm text-amber-200" role="alert">
          Indexing service is not reachable (Redis/worker). Uploads may queue but will not index until the worker is running.
        </div>
      ) : null}
      {data?.queue_wait_warning ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mb-4 text-sm" role="status">
          Waiting for the indexing service. This is taking longer than usual.
        </div>
      ) : null}

      <section
        className="admin-card p-8 border-2 border-dashed border-chat-border mb-6 text-center"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void onFiles(e.dataTransfer.files);
        }}
      >
        <label className="block text-sm text-left max-w-md mx-auto mb-4">
          <span className="font-medium">Who can see uploaded files?</span>
          <select
            className="mt-1 w-full rounded-lg border border-chat-border bg-chat-surface px-3 py-2 text-sm"
            value={visibilityMode}
            onChange={(e) => setVisibilityMode(e.target.value)}
          >
            <option value="admins_only">Admins only</option>
            <option value="all_staff">All staff</option>
          </select>
        </label>
        <button type="button" className="aq-btn-primary mt-3" disabled={uploading} onClick={() => inputRef.current?.click()}>
          {uploading ? "Uploading…" : "Choose files"}
        </button>
        <input ref={inputRef} type="file" multiple className="sr-only" aria-label="Choose files to upload" onChange={(e) => void onFiles(e.target.files)} />
      </section>

      {error ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mb-4 text-sm" role="alert">
          {error}
        </div>
      ) : null}

      {data?.counts ? (
        <p className="text-sm text-chat-muted mb-4" aria-live="polite">
          {data.counts.total} total · {data.counts.indexed} indexed · {data.counts.indexing} indexing · {data.counts.failed}{" "}
          failed
        </p>
      ) : null}

      {loading ? <p className="text-sm text-chat-muted">Loading documents…</p> : null}

      {data && data.items.length > 0 ? (
        <div className="admin-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-chat-border text-left text-chat-muted">
                <th className="p-3 font-medium">File</th>
                <th className="p-3 font-medium">Who can see</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id} className="border-b border-chat-border last:border-0">
                  <td className="p-3">
                    <p className="font-medium">{row.file_name}</p>
                    <p className="text-xs text-chat-muted">{(row.size_bytes / 1024).toFixed(1)} KB</p>
                    {row.failure_reason ? (
                      <p className="text-xs text-red-700 mt-1" role="alert">
                        {row.failure_reason}
                      </p>
                    ) : null}
                  </td>
                  <td className="p-3">{visibilityLabel(row.visibility_mode)}</td>
                  <td className="p-3">
                    <DocumentProgressCell row={row} tick={tick} />
                  </td>
                  <td className="p-3 space-x-2">
                    {row.status === "failed" || row.index_stage === "failed" || row.index_stage === "empty" ? (
                      <button
                        type="button"
                        className="text-sm text-[var(--chat-brand-mark)]"
                        onClick={() => session && retryDocument(session, row.id).then(() => load())}
                      >
                        Retry
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="text-sm text-red-700"
                      onClick={() => {
                        if (!session || !window.confirm(`Remove ${row.file_name}?`)) return;
                        removeDocument(session, row.id)
                          .then(() => {
                            setData((prev) =>
                              prev
                                ? {
                                    ...prev,
                                    items: prev.items.filter((d) => d.id !== row.id),
                                    counts: {
                                      ...prev.counts,
                                      total: Math.max(0, (prev.counts.total ?? 1) - 1),
                                      failed:
                                        row.status === "failed" || row.index_stage === "failed"
                                          ? Math.max(0, (prev.counts.failed ?? 1) - 1)
                                          : prev.counts.failed,
                                    },
                                  }
                                : prev,
                            );
                            void load({ silent: true });
                          })
                          .catch((e) => {
                            const msg = e instanceof Error ? e.message : "Remove failed";
                            if (msg === "Failed to fetch") {
                              setError(
                                "Remove may have failed (network or CORS). Refresh the page to confirm the file list.",
                              );
                            } else {
                              setError(msg);
                            }
                          });
                      }}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
