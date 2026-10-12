import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../lib/conversations";
import MarkdownContent from "./MarkdownContent";
import MessageMetaPanel from "./SourceCitations";

type Props = {
  messages: ChatMessage[];
  streamingText?: string | null;
  showScrollDown?: boolean;
  onScrollDown?: () => void;
};

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end mb-6">
      <div className="max-w-[85%] rounded-3xl bg-chat-user-bubble px-4 py-2.5 text-[15px] leading-relaxed text-chat-fg whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}

function AssistantBlock({ message, streamingText }: { message?: ChatMessage; streamingText?: string | null }) {
  const content = streamingText ?? message?.content ?? "";
  if (!content && !message?.meta) return null;

  return (
    <div className="mb-8 max-w-none">
      <div className="text-[15px] leading-relaxed text-chat-fg">
        {streamingText ? (
          <p className="whitespace-pre-wrap">{streamingText}</p>
        ) : (
          <MarkdownContent content={content} />
        )}
        {streamingText ? (
          <span className="inline-block w-2 h-4 ml-0.5 bg-chat-fg/60 animate-pulse align-middle" aria-hidden />
        ) : null}
      </div>
      {!streamingText && message ? <MessageMetaPanel meta={message.meta} /> : null}
    </div>
  );
}

export default function MessageList({ messages, streamingText, showScrollDown, onScrollDown }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: streamingText ? "auto" : "smooth" });
  }, [messages, streamingText]);

  return (
    <div ref={containerRef} className="relative flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-6">
        {messages.map((m) =>
          m.role === "user" ? (
            <UserBubble key={m.id} content={m.content} />
          ) : (
            <AssistantBlock key={m.id} message={m} />
          ),
        )}
        {streamingText != null && streamingText !== "" ? <AssistantBlock streamingText={streamingText} /> : null}
        <div ref={bottomRef} className="h-4" aria-hidden />
      </div>

      {showScrollDown ? (
        <button
          type="button"
          className="fixed bottom-28 left-1/2 z-20 -translate-x-1/2 rounded-full border border-chat-border bg-chat-surface px-3 py-1.5 text-xs shadow-composer hover:bg-chat-hover"
          onClick={onScrollDown}
        >
          Scroll to bottom
        </button>
      ) : null}
    </div>
  );
}
