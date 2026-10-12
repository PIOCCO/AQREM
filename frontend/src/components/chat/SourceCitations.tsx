import { useState } from "react";
import { Link } from "react-router-dom";
import type { ChatCitation, ChatMessageMeta } from "../../lib/conversations";
import { IconChevronRight } from "../icons/Icons";

function CitationRow({ citation }: { citation: ChatCitation }) {
  const [open, setOpen] = useState(false);
  const label = citation.fileName || citation.filePath;
  const loc =
    citation.lineStart != null
      ? ` · L${citation.lineStart}${citation.lineEnd != null ? `–${citation.lineEnd}` : ""}`
      : "";

  return (
    <div className="rounded-lg border border-chat-border bg-chat-surface-subtle text-sm">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-chat-hover transition-colors"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <IconChevronRight className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-90" : ""}`} />
        <span className="min-w-0 flex-1 truncate font-medium text-chat-fg">{label}</span>
        {citation.evidenceStrength ? (
          <span className="shrink-0 text-xs text-chat-muted capitalize">{citation.evidenceStrength}</span>
        ) : null}
        <Link
          to={`/evidence/${citation.evidenceId}`}
          className="shrink-0 text-xs text-chat-accent hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          Open
        </Link>
      </button>
      {open ? (
        <div className="border-t border-chat-border px-3 py-2 text-xs text-chat-muted whitespace-pre-wrap break-words">
          <p className="mb-1 font-mono text-[11px] text-chat-fg/80">
            {citation.filePath}
            {loc}
          </p>
          {citation.excerpt}
        </div>
      ) : null}
    </div>
  );
}

export default function MessageMetaPanel({ meta }: { meta?: ChatMessageMeta }) {
  if (!meta) return null;

  const badges: string[] = [];
  if (meta.fromLibrary && meta.libraryStatus === "approved") badges.push("Approved");
  else if (meta.isDraft) badges.push("Draft");
  if (meta.insufficientEvidence) badges.push("Insufficient evidence");

  return (
    <div className="mt-3 space-y-2">
      {badges.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {badges.map((b) => (
            <span
              key={b}
              className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                b === "Approved"
                  ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                  : b === "Insufficient evidence"
                    ? "bg-amber-500/15 text-amber-800 dark:text-amber-200"
                    : "bg-chat-surface-subtle text-chat-muted border border-chat-border"
              }`}
            >
              {b}
            </span>
          ))}
          {meta.fromLibrary && meta.libraryEntryId ? (
            <Link to={`/answer-library/${meta.libraryEntryId}`} className="text-xs text-chat-accent hover:underline">
              View library entry
            </Link>
          ) : null}
        </div>
      ) : null}

      {meta.uploadNote ? <p className="text-xs text-chat-muted">{meta.uploadNote}</p> : null}

      {meta.citations && meta.citations.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-chat-muted uppercase tracking-wide">Sources</p>
          {meta.citations.map((c) => (
            <CitationRow key={c.evidenceId} citation={c} />
          ))}
        </div>
      ) : null}

      {meta.error ? (
        <p className="text-sm text-red-600 dark:text-red-400">Something went wrong. Try sending again.</p>
      ) : null}
    </div>
  );
}
