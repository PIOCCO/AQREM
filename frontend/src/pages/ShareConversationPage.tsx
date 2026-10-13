import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import MarkdownContent from "../components/chat/MarkdownContent";
import { fetchChatShare, type ChatShareView } from "../lib/chatShareApi";
import { useAuth } from "../lib/authContext";

export default function ShareConversationPage() {
  const { shareToken } = useParams();
  const { session } = useAuth();
  const [data, setData] = useState<ChatShareView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session || !shareToken) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchChatShare(session, shareToken)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Unable to load share"))
      .finally(() => setLoading(false));
  }, [session, shareToken]);

  if (!session) return null;

  return (
    <div className="chat-view bg-chat-main">
      <header className="ref-chat-header shrink-0">
        <div className="ref-chat-header-inner">
          <div className="min-w-0">
            <p className="text-xs text-chat-muted uppercase tracking-wide">Shared conversation</p>
            <h1 className="truncate text-[15px] font-medium text-chat-fg">{data?.title ?? "Share link"}</h1>
          </div>
          <Link to="/" className="ref-header-action-btn shrink-0">
            Back to chat
          </Link>
        </div>
      </header>
      <div className="ref-conversation-scroll min-h-0 flex-1 overflow-y-auto">
        <div className="ref-conversation-column py-8">
          {loading ? (
            <p className="text-sm text-chat-muted">Loading…</p>
          ) : error ? (
            <p className="text-sm text-[var(--color-danger)]" role="alert">
              {error}
            </p>
          ) : data ? (
            <ul className="space-y-8">
              {data.messages.map((m, idx) => (
                <li key={`${m.created_at ?? idx}-${idx}`}>
                  {m.role === "user" ? (
                    <div className="ref-msg-user-wrap">
                      <div className="ref-user-bubble">{m.content}</div>
                    </div>
                  ) : (
                    <div className="ref-msg-assistant prose-chat">
                      <MarkdownContent content={m.content} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  );
}
