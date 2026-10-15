import type { AuthSession } from "./api";
import { resolveApiBase } from "./apiBase";
import { readApiError } from "./errors";
import type { ChatConversation } from "./conversations";

function apiUrl(path: string): string {
  return `${resolveApiBase()}${path}`;
}

function headers(session: AuthSession): HeadersInit {
  const h: Record<string, string> = {
    Authorization: `Bearer ${session.token}`,
    "Content-Type": "application/json",
  };
  if (session.organizationId) h["X-Organization-Id"] = session.organizationId;
  return h;
}

export type ChatShareView = {
  title: string;
  messages: { role: string; content: string; created_at?: string | null }[];
  shared_at: string;
};

export type CreateShareResult = {
  share_token: string;
  share_path: string;
};

export function shareUrlFromPath(sharePath: string): string {
  const path = sharePath.startsWith("/") ? sharePath : `/${sharePath}`;
  return `${window.location.origin}${path}`;
}

export function conversationToSharePayload(conversation: ChatConversation) {
  return {
    client_conversation_id: conversation.id,
    title: conversation.title,
    messages: conversation.messages.map((m) => ({
      role: m.role,
      content: m.content,
      created_at: m.createdAt,
    })),
  };
}

export async function createChatShare(session: AuthSession, conversation: ChatConversation): Promise<CreateShareResult> {
  const res = await fetch(apiUrl("/api/v1/chat/shares"), {
    method: "POST",
    headers: headers(session),
    body: JSON.stringify(conversationToSharePayload(conversation)),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to create share link"));
  return res.json() as Promise<CreateShareResult>;
}

export async function fetchChatShare(session: AuthSession, token: string): Promise<ChatShareView> {
  const res = await fetch(apiUrl(`/api/v1/chat/shares/${encodeURIComponent(token)}`), {
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Share link not found or access denied"));
  return res.json() as Promise<ChatShareView>;
}

export async function fetchPublicChatShare(token: string): Promise<ChatShareView> {
  const res = await fetch(apiUrl(`/api/v1/public/chat/shares/${encodeURIComponent(token)}`));
  if (!res.ok) throw new Error(await readApiError(res, "Share link not found or expired"));
  return res.json() as Promise<ChatShareView>;
}
