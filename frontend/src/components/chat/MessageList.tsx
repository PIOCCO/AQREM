import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../../lib/conversations";
import { IconCopy, IconRefresh, IconTableSheet } from "../icons/Icons";
import MarkdownContent from "./MarkdownContent";
import MessageMetaPanel from "./SourceCitations";

type Props = {
  messages: ChatMessage[];
  streamingText?: string | null;
  onRegenerate?: (userQuery: string) => void;
};

function UserMessage({ message }: { message: ChatMessage }) {
  const attachments = message.meta?.attachments ?? [];
  return (
    <div className="ref-msg-user-wrap">
      {attachments.map((a) => (
        <div key={a.name} className="ref-attachment-card">
          <IconTableSheet className="h-5 w-5 text-emerald-700 shrink-0" />
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
  previousUserText,
}: {
  message: ChatMessage;
  onRegenerate?: (q: string) => void;
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
    !message.meta.error;

  return (
    <div className="ref-msg-assistant">
      {needsReview ? (
        <div className="mb-3 flex items-center gap-2">
          <span className="ref-badge-review">Needs review</span>
        </div>
      ) : null}
      <MarkdownContent content={message.content} />
      <MessageMetaPanel meta={message.meta} variant="reference" />
      <div className="ref-msg-actions">
        <button type="button" className="ref-msg-action-btn" onClick={onCopy} aria-label="Copy">
          <IconCopy className="h-4 w-4" />
          {copied ? <span className="text-xs">Copied</span> : null}
        </button>
        {previousUserText && onRegenerate ? (
          <button
            type="button"
            className="ref-msg-action-btn"
            aria-label="Regenerate"
            onClick={() => onRegenerate(previousUserText)}
          >
            <IconRefresh className="h-4 w-4" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default function MessageList({ messages, streamingText, onRegenerate }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: streamingText ? "auto" : "smooth" });
  }, [messages, streamingText]);

  return (
    <div className="ref-conversation-scroll flex-1 overflow-y-auto">
      <div className="ref-conversation-column">
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
            />
          );
        })}
        {streamingText != null && streamingText !== "" ? (
          <div className="ref-msg-assistant">
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{streamingText}</p>
            <span className="inline-block w-2 h-4 ml-0.5 bg-chat-fg/50 animate-pulse align-middle" aria-hidden />
          </div>
        ) : null}
        <div ref={bottomRef} className="h-6" aria-hidden />
      </div>
    </div>
  );
}
