import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EvidenceStrengthBadge } from "../components/ui/Badges";
import { ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchEvidenceDetail } from "../lib/api";
import { useProjectContext } from "../lib/projectContext";

export default function EvidenceDetailPage() {
  const { evidenceId } = useParams();
  const { session } = useProjectContext();
  const [item, setItem] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session || !evidenceId) return;
    setLoading(true);
    fetchEvidenceDetail(session, evidenceId)
      .then(setItem)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load evidence"))
      .finally(() => setLoading(false));
  }, [session, evidenceId]);

  if (loading) return <LoadingState label="Loading evidence…" />;
  if (error) return <ErrorState message={error} />;
  if (!item) return null;

  const path = String(item.file_path ?? "");
  const content = String(item.content ?? "");

  return (
    <div>
      <PageHeader
        title={path || "Evidence"}
        subtitle={
          (item.repository
            ? `${String(item.repository)} · ${String(item.commit_hash ?? "").slice(0, 8)}`
            : undefined) as string | undefined
        }
        actions={
          <Link to="/evidence" className="text-sm text-blue-600 hover:underline">
            Back to evidence
          </Link>
        }
      />
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3">
        <div className="flex flex-wrap gap-2 text-sm text-slate-600">
          {item.line_start != null && (
            <span>
              Lines {String(item.line_start)}
              {item.line_end != null ? `–${String(item.line_end)}` : ""}
            </span>
          )}
          <EvidenceStrengthBadge strength={String(item.evidence_strength ?? "")} />
          {item.content_hash != null && item.content_hash !== "" ? (
            <span className="font-mono text-xs">hash {String(item.content_hash).slice(0, 12)}…</span>
          ) : null}
        </div>
        <pre className="whitespace-pre-wrap text-sm bg-slate-50 rounded-lg p-4 border border-slate-100 overflow-x-auto">
          {content}
        </pre>
      </div>
    </div>
  );
}
