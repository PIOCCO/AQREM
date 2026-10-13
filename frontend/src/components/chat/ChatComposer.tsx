import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { IconArrowUp, IconPlus, IconStop } from "../icons/Icons";
import { Tooltip } from "../ui/Tooltip";

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

const ChatComposer = forwardRef<HTMLTextAreaElement, Props>(function ChatComposer(
  {
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
  },
  forwardedRef,
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  useImperativeHandle(forwardedRef, () => textareaRef.current as HTMLTextAreaElement);

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

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (uploadDisabledReason || disabled) return;
    onPickFiles(e.dataTransfer.files);
  }

  const canSend =
    !disabled &&
    !loading &&
    (value.trim().length > 0 || attachments.some((a) => a.status === "pending"));

  const attachTitle = uploadDisabledReason ?? "Attach documents";

  return (
    <div
      className={`w-full ${centered ? "max-w-[var(--chat-column-max)] mx-auto px-4" : "max-w-[var(--chat-column-max)] mx-auto px-4 pb-4 pt-2"}`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!uploadDisabledReason && !disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
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
              {a.status === "error" ? <span className="text-[var(--color-danger)]">Failed</span> : null}
              <button
                type="button"
                className="text-chat-muted hover:text-chat-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-focus-ring)] rounded"
                onClick={() => onRemoveAttachment(a.id)}
                aria-label={`Remove ${a.file.name}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className={`chat-composer shadow-composer ${dragOver ? "ring-2 ring-[var(--color-accent)]" : ""}`}>
        <input
          ref={fileRef}
          type="file"
          multiple
          className="sr-only"
          aria-label="Attach documents"
          onChange={onFileChange}
          disabled={Boolean(uploadDisabledReason) || disabled}
        />
        <Tooltip label={attachTitle}>
          <button
            type="button"
            className="chat-composer-attach-btn shrink-0"
            onClick={() => fileRef.current?.click()}
            disabled={Boolean(uploadDisabledReason) || disabled}
            aria-label="Attach documents"
            title={attachTitle}
          >
            <IconPlus className="h-5 w-5" />
          </button>
        </Tooltip>
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
          <Tooltip label="Stop generating">
            <button
              type="button"
              className="chat-composer-send chat-composer-send-stop aq-interactive"
              onClick={onStop}
              aria-label="Stop generating"
            >
              <IconStop className="h-4 w-4" />
            </button>
          </Tooltip>
        ) : (
          <Tooltip label={canSend ? "Send message" : "Enter a message to send"}>
            <button
              type="button"
              className={`chat-composer-send aq-interactive ${canSend ? "chat-composer-send-ready" : ""}`}
              disabled={!canSend}
              onClick={onSend}
              aria-label="Send message"
            >
              {loading ? <span className="chat-spinner" aria-hidden /> : <IconArrowUp className="h-4 w-4" />}
            </button>
          </Tooltip>
        )}
      </div>
      <p className="ref-composer-disclaimer">
        AQREM can make mistakes. Verify important answers against the source evidence.
      </p>
    </div>
  );
});

export default ChatComposer;
