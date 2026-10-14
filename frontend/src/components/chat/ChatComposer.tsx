import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  type KeyboardEvent,
} from "react";
import { IconArrowUp, IconPlus, IconStop } from "../icons/Icons";
import {
  measureClampedTextareaHeight,
  scrollTextareaCaretIntoView,
} from "../../lib/composerGrow";
import { Tooltip } from "../ui/Tooltip";
import { ChatAttachmentChips } from "./ChatAttachmentChips";
import type { ChatAttachmentChip } from "../../hooks/useChatAttachments";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  streaming?: boolean;
  disabled?: boolean;
  loading?: boolean;
  attachments: ChatAttachmentChip[];
  onPickFiles: (files: File[]) => void;
  onRemoveAttachment: (id: string) => void;
  onRetryAttachment: (id: string) => void;
  uploadDisabledReason?: string | null;
  helperText?: string | null;
  sendBlocked?: boolean;
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
    onRetryAttachment,
    uploadDisabledReason,
    helperText,
    sendBlocked,
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
      if (!disabled && !loading && !sendBlocked && (value.trim() || attachments.some((a) => a.status === "ready" || a.status === "indexing"))) {
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

  function onPaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    typingUntilRef.current = Date.now() + 160;
    const items = e.clipboardData?.items;
    const files: File[] = [];
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === "file") {
          const f = item.getAsFile();
          if (f) files.push(f);
        }
      }
    }
    if (files.length) {
      e.preventDefault();
      if (!uploadDisabledReason && !disabled) onPickFiles(files);
      return;
    }
    requestAnimationFrame(() => scheduleResize());
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const list = e.target.files;
    if (list?.length) onPickFiles(Array.from(list));
    e.target.value = "";
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (uploadDisabledReason || disabled) return;
    if (e.dataTransfer.files?.length) onPickFiles(Array.from(e.dataTransfer.files));
  }

  const hasSendableAttachment = attachments.some((a) => a.status === "ready" || a.status === "indexing");
  const canSend =
    !disabled &&
    !loading &&
    !sendBlocked &&
    (value.trim().length > 0 || hasSendableAttachment);

  const attachTitle = uploadDisabledReason ?? "Attach documents";
  const accept = ".pdf,.md,.txt,text/plain,text/markdown,application/pdf";

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
      {helperText ? (
        <p className="text-xs text-chat-muted mb-2 px-1">{helperText}</p>
      ) : null}
      <div
        ref={shellRef}
        className={`chat-composer shadow-composer ${dragOver ? "ring-2 ring-[var(--color-accent)]" : ""}`}
        data-testid="chat-composer-shell"
      >
        <ChatAttachmentChips attachments={attachments} onRemove={onRemoveAttachment} onRetry={onRetryAttachment} />

        <div className="chat-composer-row">
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={accept}
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
            <Tooltip label={canSend ? "Send message" : sendBlocked ? "Wait for uploads to finish" : "Enter a message to send"}>
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
