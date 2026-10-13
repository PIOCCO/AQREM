import { useCallback, useEffect, useId, useRef, useState } from "react";
import { IconCopy } from "../icons/Icons";
import { createChatShare, shareUrlFromPath } from "../../lib/chatShareApi";
import { copyToClipboard } from "../../lib/copyToClipboard";
import type { ChatConversation } from "../../lib/conversations";
import type { AuthSession } from "../../lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
  session: AuthSession;
  conversation: ChatConversation | null;
  anchorRef?: React.RefObject<HTMLElement | null>;
};

export default function ShareConversationDialog({ open, onClose, session, conversation, anchorRef }: Props) {
  const titleId = useId();
  const descId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const [shareUrl, setShareUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [copyError, setCopyError] = useState<string | null>(null);
  const [panelStyle, setPanelStyle] = useState<{ top: number; left: number; maxWidth: number } | null>(null);

  const loadShare = useCallback(async () => {
    if (!conversation) return;
    setLoading(true);
    setError(null);
    setCopyState("idle");
    setCopyError(null);
    try {
      const result = await createChatShare(session, conversation);
      setShareUrl(shareUrlFromPath(result.share_path));
    } catch (e) {
      setShareUrl("");
      setError(e instanceof Error ? e.message : "Could not create share link");
    } finally {
      setLoading(false);
    }
  }, [conversation, session]);

  useEffect(() => {
    if (!open) return;
    void loadShare();
  }, [open, loadShare]);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !anchorRef?.current || !panelRef.current) {
      setPanelStyle(null);
      return;
    }
    function position() {
      if (!anchorRef?.current) return;
      const anchor = anchorRef.current.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const width = Math.min(400, vw - 24);
      let left = anchor.right - width;
      left = Math.max(12, Math.min(left, vw - width - 12));
      let top = anchor.bottom + 8;
      const panelH = panelRef.current?.offsetHeight ?? 280;
      if (top + panelH > vh - 12) top = Math.max(12, anchor.top - panelH - 8);
      setPanelStyle({ top, left, maxWidth: width });
    }
    position();
    window.addEventListener("resize", position);
    return () => window.removeEventListener("resize", position);
  }, [open, anchorRef, loading, error, shareUrl]);

  async function onCopy() {
    if (!shareUrl) return;
    const result = await copyToClipboard(shareUrl);
    if (result.ok) {
      setCopyState("copied");
      setCopyError(null);
      window.setTimeout(() => setCopyState("idle"), 2000);
    } else {
      setCopyState("failed");
      setCopyError(result.error);
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }

  if (!open) return null;

  const noConversation = !conversation;

  return (
    <div className="fixed inset-0 z-[70]" role="presentation">
      <button type="button" className="absolute inset-0 bg-black/40" aria-label="Close share dialog" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        className="aq-modal absolute w-full max-w-[400px] p-4 shadow-composer border border-chat-border bg-chat-surface rounded-xl"
        style={
          panelStyle
            ? { top: panelStyle.top, left: panelStyle.left, maxWidth: panelStyle.maxWidth }
            : { top: "50%", left: "50%", transform: "translate(-50%, -50%)", maxWidth: "min(400px, calc(100vw - 24px))" }
        }
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2 mb-3">
          <h2 id={titleId} className="aq-modal-title text-base font-semibold text-chat-fg">
            Share conversation
          </h2>
          <button
            ref={closeRef}
            type="button"
            className="ref-header-icon-btn shrink-0"
            aria-label="Close"
            onClick={onClose}
          >
            <span aria-hidden className="text-lg leading-none">
              ×
            </span>
          </button>
        </div>
        <p id={descId} className="text-sm text-chat-muted mb-4">
          Anyone in your organization who has this link and is signed in can view a read-only snapshot of this
          conversation. Links do not make chats public on the internet.
        </p>

        {noConversation ? (
          <p className="text-sm text-chat-fg">Start or open a conversation before sharing.</p>
        ) : loading ? (
          <p className="text-sm text-chat-muted" role="status">
            Preparing share link…
          </p>
        ) : error ? (
          <p className="text-sm text-[var(--color-danger)]" role="alert">
            {error}
          </p>
        ) : (
          <>
            <label className="sr-only" htmlFor={`${titleId}-url`}>
              Shareable link
            </label>
            <input
              id={`${titleId}-url`}
              ref={inputRef}
              readOnly
              value={shareUrl}
              className="chat-sidebar-search w-full mb-3 text-sm"
              onFocus={(e) => e.target.select()}
            />
            {copyState === "failed" && copyError ? (
              <p className="text-xs text-[var(--color-danger)] mb-2" role="alert">
                {copyError}. Select the link above and copy manually (Ctrl+C / ⌘C).
              </p>
            ) : copyState === "copied" ? (
              <p className="text-xs text-[var(--color-success)] mb-2" role="status">
                Link copied to clipboard.
              </p>
            ) : null}
            <button
              type="button"
              className="ref-header-action-btn w-full justify-center aq-interactive"
              onClick={() => void onCopy()}
              disabled={!shareUrl}
            >
              <IconCopy className="h-4 w-4" />
              {copyState === "copied" ? "Copied!" : "Copy link"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
