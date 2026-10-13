import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Tooltip } from "../ui/Tooltip";
import type { ChatMessage } from "../../lib/conversations";
import {
  IconCopy,
  IconRefresh,
  IconTableSheet,
  IconThumbDown,
  IconThumbUp,
} from "../icons/Icons";
import MarkdownContent from "./MarkdownContent";
import MessageMetaPanel from "./SourceCitations";
import ChatMainColumn from "./ChatMainColumn";

type Props = {
  messages: ChatMessage[];
  streamingText?: string | null;
  retrievalStatus?: string | null;
  onRegenerate?: (userQuery: string) => void;
  onRetry?: () => void;
  onFeedback?: (messageId: string, feedback: "good" | "bad") => void;
};

function UserMessage({ message }: { message: ChatMessage }) {
  const attachments = message.meta?.attachments ?? [];
  return (
    <div className="ref-msg-user-wrap">
      {attachments.map((a) => (
        <div key={a.name} className="ref-attachment-card">
          <IconTableSheet className="h-5 w-5 shrink-0 text-[var(--chat-brand-mark)]" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-chat-fg">{a.name}</p>
            {a.sizeLabel ? <p className="text-xs text-chat-muted">{a.sizeLabel}</p> : null}
          </div>
        </div>
      ))}
      <div className="ref-user-bubble">{message.content}</div>
    </div>
  );
}

function AssistantMessage({
  message,
  onRegenerate,
  onFeedback,
  onRetry,
  previousUserText,
}: {
  message: ChatMessage;
  onRegenerate?: (q: string) => void;
  onFeedback?: (messageId: string, feedback: "good" | "bad") => void;
  onRetry?: () => void;
  previousUserText?: string;
}) {
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }, [message.content]);

  const needsReview =
    message.meta?.isDraft &&
    !message.meta.fromLibrary &&
    !message.meta.insufficientEvidence &&
    !message.meta.conversational &&
    !message.meta.error;

  const showReviewQueue =
    !message.meta?.insufficientEvidence &&
    !message.meta?.conversational &&
    Boolean(message.meta?.needsReview || message.meta?.isDraft);

  return (
    <div className="ref-msg-assistant">
      {needsReview ? (
        <div className="mb-3 flex items-center gap-2">
          <Link to="/review-queue" className="ref-badge-review aq-interactive hover:opacity-90">
            Needs review — open queue
          </Link>
        </div>
      ) : null}
      <MarkdownContent content={message.content} />
      {message.meta?.conversational && message.meta.starterPrompts?.length ? (
        <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Suggested prompts">
          {message.meta.starterPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="ref-starter-prompt inline-block max-w-full"
              onClick={() => {
                window.dispatchEvent(new CustomEvent("aqrem-fill-composer", { detail: prompt }));
              }}
            >
              {prompt}
            </button>
          ))}
        </div>
      ) : null}
      <MessageMetaPanel meta={message.meta} variant="reference" />
      {message.meta?.error && onRetry ? (
        <button type="button" className="ref-evidence-action-btn mt-3" onClick={onRetry}>
          Retry
        </button>
      ) : null}
      <div className="ref-msg-actions" role="toolbar" aria-label="Message actions">
        <button
          type="button"
          className="ref-msg-action-btn"
          onClick={onCopy}
          aria-label={copied ? "Copied" : "Copy answer"}
          title={copied ? "Copied" : "Copy"}
        >
          <IconCopy className="h-4 w-4" />
          {copied ? <span className="text-xs">Copied</span> : null}
        </button>
        <button
          type="button"
          className={`ref-msg-action-btn ${message.meta?.feedback === "good" ? "ref-msg-action-btn-active" : ""}`}
          aria-label="Good answer"
          title="Good answer"
          onClick={() => onFeedback?.(message.id, "good")}
        >
          <IconThumbUp className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={`ref-msg-action-btn ${message.meta?.feedback === "bad" ? "ref-msg-action-btn-active" : ""}`}
          aria-label="Bad answer"
          title="Bad answer"
          onClick={() => onFeedback?.(message.id, "bad")}
        >
          <IconThumbDown className="h-4 w-4" />
        </button>
        {previousUserText && onRegenerate ? (
          <button
            type="button"
            className="ref-msg-action-btn"
            aria-label="Regenerate"
            title="Regenerate"
            onClick={() => onRegenerate(previousUserText)}
          >
            <IconRefresh className="h-4 w-4" />
          </button>
        ) : null}
        {showReviewQueue ? (
          <Link to="/review-queue" className="ref-msg-action-btn" title="Send to Review Queue" aria-label="Send to Review Queue">
            Review Queue
          </Link>
        ) : null}
      </div>
    </div>
  );
}

export default function MessageList({
  messages,
  streamingText,
  retrievalStatus,
  onRegenerate,
  onRetry,
  onFeedback,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const liveRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollDown, setShowScrollDown] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: streamingText ? "auto" : "smooth" });
  }, [messages, streamingText, retrievalStatus]);

  useEffect(() => {
    function onComposerResize() {
      const node = scrollContainerRef.current;
      if (!node) return;
      const maxScroll = node.scrollHeight - node.clientHeight;
      if (maxScroll <= 0) return;
      const dist = maxScroll - node.scrollTop;
      if (dist < 120) {
        node.scrollTop = maxScroll;
      }
    }
    window.addEventListener("aqrem-composer-resize", onComposerResize);
    return () => window.removeEventListener("aqrem-composer-resize", onComposerResize);
  }, []);

  useEffect(() => {
    const scrollEl = scrollContainerRef.current;
    if (!scrollEl) return;
    function onScroll() {
      const node = scrollContainerRef.current;
      if (!node) return;
      const dist = node.scrollHeight - node.scrollTop - node.clientHeight;
      setShowScrollDown(dist > 120);
    }
    scrollEl.addEventListener("scroll", onScroll);
    onScroll();
    return () => scrollEl.removeEventListener("scroll", onScroll);
  }, [messages.length]);

  useEffect(() => {
    if (streamingText && liveRef.current) {
      liveRef.current.textContent = streamingText;
    }
  }, [streamingText]);

  return (
    <div ref={scrollContainerRef} className="ref-conversation-scroll min-h-0 min-w-0 overflow-y-auto relative">
      {showScrollDown ? (
        <Tooltip label="Scroll to latest">
          <button
            type="button"
            className="ref-scroll-bottom-btn"
            onClick={() => bottomRef.current?.scrollIntoView({ behavior: "smooth" })}
            aria-label="Scroll to latest messages"
          >
            ↓
          </button>
        </Tooltip>
      ) : null}
      <ChatMainColumn className="ref-conversation-column" data-testid="chat-messages-column">
        <div>
        {messages.map((m, idx) => {
          const prevUser =
            m.role === "assistant"
              ? [...messages.slice(0, idx)].reverse().find((x) => x.role === "user")?.content
              : undefined;
          if (m.role === "user") {
            return <UserMessage key={m.id} message={m} />;
          }
          return (
            <AssistantMessage
              key={m.id}
              message={m}
              previousUserText={prevUser}
              onRegenerate={onRegenerate}
              onFeedback={onFeedback}
              onRetry={m.meta?.error ? onRetry : undefined}
            />
          );
        })}
        {retrievalStatus ? (
          <p className="ref-retrieval-status text-sm text-chat-muted mb-4" role="status" aria-live="polite">
            <span className="chat-spinner mr-2 align-middle" aria-hidden />
            {retrievalStatus}
          </p>
        ) : null}
        {streamingText != null && streamingText !== "" ? (
          <div className="ref-msg-assistant" aria-live="polite" aria-busy="true">
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{streamingText}</p>
            <span className="ref-stream-cursor" aria-hidden />
            <div className="sr-only" ref={liveRef} />
          </div>
        ) : null}
        <div ref={bottomRef} className="h-6" aria-hidden />
        </div>
      </ChatMainColumn>
    </div>
  );
}
