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
} from "react";
import { IconArrowUp, IconPlus, IconStop } from "../icons/Icons";
import {
  measureClampedTextareaHeight,
  scrollTextareaCaretIntoView,
} from "../../lib/composerGrow";
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
  conversationKey?: string | null;
};

const COMPOSER_MIN_TEXT_PX = 24;

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
    conversationKey,
  },
  forwardedRef,
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const typingUntilRef = useRef(0);
  const resizeFrameRef = useRef<number | null>(null);
  const lastShellHeightRef = useRef<number | null>(null);

  useImperativeHandle(forwardedRef, () => textareaRef.current as HTMLTextAreaElement);

  const notifyComposerResize = useCallback(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const h = shell.getBoundingClientRect().height;
    if (lastShellHeightRef.current != null && Math.abs(h - lastShellHeightRef.current) > 0.5) {
      window.dispatchEvent(new CustomEvent("aqrem-composer-resize"));
    }
    lastShellHeightRef.current = h;
  }, []);

  const applyTextareaHeight = useCallback(
    (opts?: { instant?: boolean }) => {
      const el = textareaRef.current;
      const shell = shellRef.current;
      if (!el || !shell) return;

      const instant = opts?.instant ?? false;
      const typing = Date.now() < typingUntilRef.current;
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const animate = !instant && !typing && !reduceMotion;

      shell.classList.toggle("chat-composer--height-anim", animate);
      el.classList.toggle("chat-composer-input--height-anim", animate);

      if (!value.trim()) {
        el.style.height = `${COMPOSER_MIN_TEXT_PX}px`;
      } else {
        el.style.height = `${measureClampedTextareaHeight(el)}px`;
      }

      scrollTextareaCaretIntoView(el);
      notifyComposerResize();
    },
    [notifyComposerResize, value],
  );

  const scheduleResize = useCallback(
    (opts?: { instant?: boolean }) => {
      if (resizeFrameRef.current != null) cancelAnimationFrame(resizeFrameRef.current);
      resizeFrameRef.current = requestAnimationFrame(() => {
        resizeFrameRef.current = requestAnimationFrame(() => {
          resizeFrameRef.current = null;
          applyTextareaHeight(opts);
        });
      });
    },
    [applyTextareaHeight],
  );

  useEffect(() => {
    scheduleResize({ instant: !value.trim() });
  }, [value, attachments.length, scheduleResize]);

  useEffect(() => {
    scheduleResize({ instant: true });
  }, [conversationKey, scheduleResize]);

  useEffect(() => {
    const onResize = () => scheduleResize();
    window.addEventListener("resize", onResize);
    const onSidebar = () => window.setTimeout(() => scheduleResize(), 220);
    window.addEventListener("aqrem-sidebar-transition-end", onSidebar);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("aqrem-sidebar-transition-end", onSidebar);
    };
  }, [scheduleResize]);

  useEffect(() => {
    return () => {
      if (resizeFrameRef.current != null) cancelAnimationFrame(resizeFrameRef.current);
    };
  }, []);

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key.length === 1 || e.key === "Backspace" || e.key === "Delete" || e.key === "Enter") {
      typingUntilRef.current = Date.now() + 160;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      textareaRef.current?.blur();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && !loading && (value.trim() || attachments.some((a) => a.status === "pending"))) {
        onSend();
        requestAnimationFrame(() => {
          scheduleResize({ instant: true });
          textareaRef.current?.focus();
        });
      }
    }
  }

  function onInput(e: ChangeEvent<HTMLTextAreaElement>) {
    onChange(e.target.value);
    scheduleResize();
  }

  function onPaste() {
    typingUntilRef.current = Date.now() + 160;
    requestAnimationFrame(() => scheduleResize());
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
      className="chat-composer-block"
      onDragOver={(e) => {
        e.preventDefault();
        if (!uploadDisabledReason && !disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      <div
        ref={shellRef}
        className={`chat-composer shadow-composer ${dragOver ? "ring-2 ring-[var(--color-accent)]" : ""}`}
        data-testid="chat-composer-shell"
      >
        {attachments.length > 0 ? (
          <ul className="chat-composer-attachments" aria-label="Attached files">
            {attachments.map((a) => (
              <li key={a.id} className="chat-composer-attachment-chip">
                <span className="max-w-[12rem] truncate">{a.file.name}</span>
                <span className="text-chat-muted shrink-0">
                  {a.file.size ? `${Math.max(1, Math.round(a.file.size / 1024))} KB` : ""}
                </span>
                {a.status === "uploading" ? <span className="chat-spinner" aria-label="Uploading" /> : null}
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

        <div className="chat-composer-row">
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
            >
              <IconPlus className="h-5 w-5" />
            </button>
          </Tooltip>
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={onInput}
            onKeyDown={onKeyDown}
            onPaste={onPaste}
            placeholder="Ask AQREM anything about your documents…"
            disabled={disabled}
            className="chat-composer-input"
            aria-label="Message"
            data-testid="chat-composer-input"
          />
          {streaming ? (
            <Tooltip label="Stop generating">
              <button
                type="button"
                className="chat-composer-send chat-composer-send-stop aq-interactive"
                onClick={onStop}
                aria-label="Stop generating"
                data-testid="chat-composer-stop"
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
                data-testid="chat-composer-send"
              >
                {loading ? <span className="chat-spinner" aria-hidden /> : <IconArrowUp className="h-4 w-4" />}
              </button>
            </Tooltip>
          )}
        </div>
      </div>
      <p className="ref-composer-disclaimer">
        AQREM can make mistakes. Verify important answers against the source evidence.
      </p>
    </div>
  );
});

export default ChatComposer;
