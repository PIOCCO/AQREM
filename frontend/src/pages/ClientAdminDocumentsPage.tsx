import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/authContext";
import { fetchDocuments, removeDocument, retryDocument, uploadDocuments } from "../lib/orgAdminApi";

const ALLOWED_HINT = "PDF, Markdown, plain text, and .tar.gz archives";
const MAX_MB = 50;

function statusLabel(status: string) {
  switch (status) {
    case "uploading":
      return "Uploading";
    case "indexing":
      return "Indexing";
    case "indexed":
      return "Indexed";
    case "failed":
      return "Failed";
    default:
      return status;
  }
}

export default function ClientAdminDocumentsPage() {
  const { session } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{
    items: Array<{
      id: string;
      file_name: string;
      size_bytes: number;
      status: string;
      index_progress: number;
      failure_reason: string | null;
    }>;
    total: number;
    counts: Record<string, number>;
  } | null>(null);
  const [uploading, setUploading] = useState(false);

  const load = useCallback(() => {
    if (!session) return;
    setLoading(true);
    fetchDocuments(session, page, 10)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
      .finally(() => setLoading(false));
  }, [session, page]);

  useEffect(() => {
    load();
  }, [load]);

  async function onFiles(files: FileList | null) {
    if (!session || !files?.length) return;
    setError(null);
    setUploading(true);
    try {
      await uploadDocuments(session, files);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
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

      <section
        className="admin-card p-8 border-2 border-dashed border-chat-border mb-6 text-center"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void onFiles(e.dataTransfer.files);
        }}
      >
        <p className="text-sm font-medium">Drag and drop files here</p>
        <p className="text-xs text-chat-muted mt-1">or</p>
        <button
          type="button"
          className="aq-btn-primary mt-3"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? "Uploading…" : "Choose files"}
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="sr-only"
          aria-label="Choose files to upload"
          onChange={(e) => void onFiles(e.target.files)}
        />
      </section>

      {error ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mb-4 text-sm" role="alert">
          {error}
        </div>
      ) : null}

      {data?.counts ? (
        <p className="text-sm text-chat-muted mb-4">
          {data.counts.total} total · {data.counts.indexed} indexed · {data.counts.indexing} indexing ·{" "}
          {data.counts.failed} failed
        </p>
      ) : null}

      {loading ? <p className="text-sm text-chat-muted">Loading documents…</p> : null}

      {!loading && data && data.items.length === 0 ? (
        <p className="text-sm text-chat-muted admin-card p-6">No documents yet. Upload your first file above.</p>
      ) : null}

      {data && data.items.length > 0 ? (
        <div className="admin-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-chat-border text-left text-chat-muted">
                <th className="p-3 font-medium">File</th>
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
                  <td className="p-3">
                    {statusLabel(row.status)}
                    {row.status === "indexing" ? (
                      <span className="text-xs text-chat-muted ml-2">{row.index_progress}%</span>
                    ) : null}
                  </td>
                  <td className="p-3 space-x-2">
                    {row.status === "failed" ? (
                      <button
                        type="button"
                        className="text-sm text-[var(--chat-brand-mark)]"
                        onClick={() => session && retryDocument(session, row.id).then(load)}
                      >
                        Retry
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="text-sm text-red-700"
                      onClick={() => {
                        if (!session || !window.confirm(`Remove ${row.file_name}?`)) return;
                        removeDocument(session, row.id).then(load).catch((e) => setError(String(e)));
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

      {data && data.total > 10 ? (
        <div className="flex gap-2 mt-4">
          <button type="button" className="aq-btn-secondary text-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <button
            type="button"
            className="aq-btn-secondary text-sm"
            disabled={page * 10 >= data.total}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}
