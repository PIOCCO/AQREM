import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ChatCitation, ChatMessageMeta } from "../../lib/conversations";
import { IconChevronDown, IconSource } from "../icons/Icons";

const HIGHLIGHT_TERMS = [
  "AES-256",
  "TLS 1.2",
  "TLS 1.3",
  "encrypted at rest",
  "encryption",
  "multi-factor",
  "MFA",
];

function highlightExcerpt(text: string): ReactNode {
  let parts: ReactNode[] = [text];
  for (const term of HIGHLIGHT_TERMS) {
    const next: ReactNode[] = [];
    for (const part of parts) {
      if (typeof part !== "string") {
        next.push(part);
        continue;
      }
      const re = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
      const split = part.split(re);
      split.forEach((chunk, i) => {
        if (i % 2 === 1) next.push(<mark key={`${term}-${i}`} className="ref-evidence-mark">{chunk}</mark>);
        else if (chunk) next.push(chunk);
      });
    }
    parts = next;
  }
  return parts;
}

function SourcePill({ citation }: { citation: ChatCitation }) {
  const label = citation.fileName || citation.filePath.split("/").pop() || "Source";
  const page =
    citation.lineStart != null
      ? `p. ${citation.lineStart}${citation.lineEnd && citation.lineEnd !== citation.lineStart ? `–${citation.lineEnd}` : ""}`
      : null;
  return (
    <Link to={`/evidence/${citation.evidenceId}`} className="ref-source-pill">
      <IconSource className="h-3.5 w-3.5 shrink-0 opacity-70" />
      <span className="truncate max-w-[14rem]">{label}</span>
      {page ? <span className="text-chat-muted shrink-0">{page}</span> : null}
    </Link>
  );
}

function EvidencePreview({ citation }: { citation: ChatCitation }) {
  const [open, setOpen] = useState(false);
  const label = citation.fileName || citation.filePath;

  return (
    <div className="ref-evidence-preview">
      <button type="button" className="ref-evidence-preview-toggle" onClick={() => setOpen((v) => !v)}>
        <span className="text-sm text-chat-muted">Evidence preview — {label}</span>
        <IconChevronDown className={`h-4 w-4 text-chat-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="ref-evidence-preview-body">
          <p className="text-[13px] leading-relaxed text-chat-fg whitespace-pre-wrap">
            {highlightExcerpt(citation.excerpt)}
          </p>
          <Link to={`/evidence/${citation.evidenceId}`} className="text-xs text-chat-accent hover:underline mt-2 inline-block">
            Open full evidence
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export default function MessageMetaPanel({
  meta,
  variant = "default",
}: {
  meta?: ChatMessageMeta;
  variant?: "default" | "reference";
}) {
  if (!meta) return null;

  const badges: string[] = [];
  if (meta.fromLibrary && meta.libraryStatus === "approved") badges.push("Approved");
  else if (meta.insufficientEvidence) badges.push("Insufficient evidence");

  const citations = meta.citations ?? [];

  return (
    <div className="mt-4 space-y-3">
      {badges.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {badges.map((b) => (
            <span key={b} className="ref-badge-muted">
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

      {citations.length > 0 && variant === "reference" ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-chat-muted">Sources</span>
            {citations.map((c) => (
              <SourcePill key={c.evidenceId} citation={c} />
            ))}
          </div>
          {citations[0] ? <EvidencePreview citation={citations[0]} /> : null}
        </>
      ) : null}

      {citations.length > 0 && variant === "default" ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-chat-muted uppercase tracking-wide">Sources</p>
          {citations.map((c) => (
            <EvidencePreview key={c.evidenceId} citation={c} />
          ))}
        </div>
      ) : null}

      {meta.error ? <p className="text-sm text-red-600">Something went wrong. Try again.</p> : null}
    </div>
  );
}
