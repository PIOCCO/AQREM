import { useCallback, useEffect, useRef, type ChangeEvent, type KeyboardEvent, type ReactNode } from "react";
import { IconArrowUp, IconPlus, IconStop } from "../icons/Icons";

export type PendingAttachment = {
  id: string;
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
};

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  streaming?: boolean;
  disabled?: boolean;
  loading?: boolean;
  attachments: PendingAttachment[];
  onPickFiles: (files: FileList | null) => void;
  onRemoveAttachment: (id: string) => void;
  uploadDisabledReason?: string | null;
  centered?: boolean;
  scopeSlot?: ReactNode;
};

const MAX_LINES = 8;
const LINE_HEIGHT_PX = 24;

export default function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  streaming,
  disabled,
  loading,
  attachments,
  onPickFiles,
  onRemoveAttachment,
  uploadDisabledReason,
  centered,
  scopeSlot,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = LINE_HEIGHT_PX * MAX_LINES;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [value, resize]);

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && !loading && (value.trim() || attachments.some((a) => a.status === "pending"))) onSend();
    }
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    onPickFiles(e.target.files);
    e.target.value = "";
  }

  const canSend =
    !disabled &&
    !loading &&
    (value.trim().length > 0 || attachments.some((a) => a.status === "pending"));

  return (
    <div
      className={`w-full ${centered ? "max-w-[var(--chat-column-max)] mx-auto px-4" : "max-w-[var(--chat-column-max)] mx-auto px-4 pb-4 pt-2"}`}
    >
      {scopeSlot ? <div className="mb-3">{scopeSlot}</div> : null}
      {attachments.length > 0 ? (
        <ul className="mb-2 flex flex-wrap gap-2">
          {attachments.map((a) => (
            <li
              key={a.id}
              className="flex items-center gap-2 rounded-full border border-chat-border bg-chat-surface-subtle px-3 py-1 text-xs text-chat-fg"
            >
              <span className="max-w-[12rem] truncate">{a.file.name}</span>
              {a.status === "uploading" ? <span className="chat-spinner" aria-hidden /> : null}
              {a.status === "error" ? <span className="text-[var(--chat-danger-fg)]">Failed</span> : null}
              <button
                type="button"
                className="text-chat-muted hover:text-chat-fg focus-visible:ref-focus-ring rounded"
                onClick={() => onRemoveAttachment(a.id)}
                aria-label={`Remove ${a.file.name}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="chat-composer shadow-composer">
        <input
          ref={fileRef}
          type="file"
          multiple
          className="sr-only"
          onChange={onFileChange}
          disabled={Boolean(uploadDisabledReason) || disabled}
        />
        <button
          type="button"
          className="chat-composer-attach-btn shrink-0"
          onClick={() => fileRef.current?.click()}
          disabled={Boolean(uploadDisabledReason) || disabled}
          title={uploadDisabledReason ?? "Attach documents"}
          aria-label="Attach documents"
        >
          <IconPlus className="h-5 w-5" />
        </button>
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask AQREM anything about your documents…"
          disabled={disabled}
          className="chat-composer-input"
          aria-label="Message"
        />
        {streaming ? (
          <button type="button" className="chat-composer-send chat-composer-send-stop" onClick={onStop} aria-label="Stop generating">
            <IconStop className="h-4 w-4" />
            <span className="sr-only">Stop</span>
          </button>
        ) : (
          <button
            type="button"
            className={`chat-composer-send ${canSend ? "chat-composer-send-ready" : ""}`}
            disabled={!canSend}
            onClick={onSend}
            aria-label="Send message"
          >
            {loading ? <span className="chat-spinner" aria-hidden /> : <IconArrowUp className="h-4 w-4" />}
          </button>
        )}
      </div>
      <p className="ref-composer-disclaimer">
        AQREM can make mistakes. Verify important answers against the source evidence.
      </p>
    </div>
  );
}
