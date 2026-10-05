import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EvidenceStrengthBadge } from "../components/ui/Badges";
import { ErrorState, LoadingState, PageHeader } from "../components/ui/States";
import { fetchEvidenceDetail } from "../lib/api";
import { splitLinesLimited } from "../lib/textPreview";
import { useProjectContext } from "../lib/projectContext";

const MAX_LINES = 200;

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
  }, [session?.organizationId, session?.token, evidenceId]);

  if (loading) return <LoadingState label="Loading evidence…" />;
  if (error) return <ErrorState message={error} />;
  if (!item) return <ErrorState message="Evidence not found." />;

  const path = String(item.file_path ?? "");
  const content = String(item.content ?? "");
  const apiTruncated = Boolean(item.content_truncated);
  const { lines, truncated } = splitLinesLimited(content, MAX_LINES);
  const showTruncated = apiTruncated || truncated;
  const lineStart = item.line_start != null ? Number(item.line_start) : null;

  return (
    <div>
      <PageHeader
        title={path || "Evidence"}
        subtitle={
          item.repository
            ? `${String(item.repository)} · ${String(item.commit_hash ?? "").slice(0, 8)}`
            : undefined
        }
        actions={
          <Link to="/evidence" className="aq-btn-secondary text-sm">
            Back to evidence
          </Link>
        }
      />
      <div className="aq-card aq-card-p space-y-4">
        <div className="flex flex-wrap gap-2 text-sm text-slate-600 items-center">
          {lineStart != null && (
            <span className="font-mono text-xs">
              Lines {String(item.line_start)}
              {item.line_end != null ? `–${String(item.line_end)}` : ""}
            </span>
          )}
          <EvidenceStrengthBadge strength={String(item.evidence_strength ?? "")} />
        </div>
        {showTruncated && (
          <p className="aq-alert-warning text-sm">
            {apiTruncated
              ? "File body was truncated for browser performance."
              : `Showing first ${MAX_LINES} lines only.`}{" "}
            Use source export for full files.
          </p>
        )}
        <div className="aq-code-block p-0 overflow-hidden max-h-[70vh] overflow-y-auto">
          <table className="w-full text-xs">
            <tbody>
              {lines.map((line, i) => {
                const lineNo = lineStart != null ? lineStart + i : i + 1;
                return (
                  <tr key={lineNo} className="align-top">
                    <td className="select-none text-slate-400 text-right pr-3 py-0.5 w-12 border-r border-border bg-surface-subtle/80">
                      {lineNo}
                    </td>
                    <td className="py-0.5 pl-3 whitespace-pre-wrap break-all">{line || " "}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
