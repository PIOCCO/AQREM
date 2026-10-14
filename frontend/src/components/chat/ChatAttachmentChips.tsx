import { memo } from "react";
import type { ChatAttachmentChip } from "../../hooks/useChatAttachments";

type Props = {
  attachments: ChatAttachmentChip[];
  onRemove: (clientId: string) => void;
  onRetry: (clientId: string) => void;
};

function statusLabel(a: ChatAttachmentChip): string {
  switch (a.status) {
    case "queued":
      return "Waiting…";
    case "uploading":
      return "Uploading…";
    case "indexing":
      return "Indexing…";
    case "ready":
      return "Ready";
    case "failed":
      return "Failed";
    default:
      return a.status;
  }
}

function ChatAttachmentChipsInner({ attachments, onRemove, onRetry }: Props) {
  if (!attachments.length) return null;
  return (
    <ul className="chat-composer-attachments" aria-label="Attached files" aria-live="polite">
      {attachments.map((a) => (
        <li key={a.clientId} className="chat-composer-attachment-chip">
          <span className="shrink-0 text-chat-muted" aria-hidden>
            📄
          </span>
          <span className="max-w-[10rem] truncate" title={a.file.name}>
            {a.file.name}
          </span>
          <span className="text-chat-muted shrink-0 text-xs">
            {a.file.size ? `${Math.max(1, Math.round(a.file.size / 1024))} KB` : ""}
          </span>
          <span className="text-xs shrink-0">{statusLabel(a)}</span>
          {a.status === "uploading" || a.status === "indexing" ? (
            <span className="chat-spinner" aria-label={statusLabel(a)} />
          ) : null}
          {a.status === "failed" ? (
            <>
              <span className="text-[var(--color-danger)] text-xs max-w-[8rem] truncate" title={a.error}>
                {a.error ?? "Failed"}
              </span>
              <button type="button" className="text-xs underline text-chat-fg" onClick={() => onRetry(a.clientId)}>
                Retry
              </button>
            </>
          ) : null}
          <button
            type="button"
            className="text-chat-muted hover:text-chat-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-focus-ring)] rounded"
            onClick={() => onRemove(a.clientId)}
            aria-label={`Remove ${a.file.name}`}
          >
            ×
          </button>
        </li>
      ))}
    </ul>
  );
}

export const ChatAttachmentChips = memo(ChatAttachmentChipsInner);
