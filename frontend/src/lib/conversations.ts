import { newUuid } from "./uuid";

export type ChatCitation = {
  evidenceId: string;
  fileName?: string;
  filePath: string;
  lineStart?: number;
  lineEnd?: number;
  excerpt: string;
  evidenceStrength?: string;
};

export type ChatMessageRole = "user" | "assistant" | "system";

export type ChatAttachmentMeta = {
  name: string;
  sizeLabel?: string;
};

export type ChatMessageMeta = {
  attachments?: ChatAttachmentMeta[];
  /** Draft from retrieval / library — not human-approved */
  isDraft?: boolean;
  /** Reused approved library answer */
  fromLibrary?: boolean;
  libraryEntryId?: string;
  libraryStatus?: string;
  insufficientEvidence?: boolean;
  conversational?: boolean;
  intent?: string;
  outcome?: string;
  needsReview?: boolean;
  citations?: ChatCitation[];
  error?: boolean;
  uploadNote?: string;
  projectName?: string;
  sourcesSearched?: number;
  queryTimeMs?: number;
  userQuery?: string;
  feedback?: "good" | "bad";
};

export type ChatMessage = {
  id: string;
  role: ChatMessageRole;
  content: string;
  createdAt: string;
  meta?: ChatMessageMeta;
};

export type ChatConversation = {
  id: string;
  title: string;
  projectId: string | null;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
};

const STORAGE_KEY = "aqrem_chat_conversations_v1";

function readAll(): ChatConversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatConversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(conversations: ChatConversation[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

export function listConversations(): ChatConversation[] {
  return readAll().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getConversation(id: string): ChatConversation | null {
  return readAll().find((c) => c.id === id) ?? null;
}

export function createConversation(projectId: string | null = null): ChatConversation {
  const now = new Date().toISOString();
  const conv: ChatConversation = {
    id: newUuid(),
    title: "New chat",
    projectId,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
  const all = readAll();
  all.unshift(conv);
  writeAll(all);
  return conv;
}

export function saveConversation(conversation: ChatConversation) {
  const all = readAll();
  const idx = all.findIndex((c) => c.id === conversation.id);
  const next = { ...conversation, updatedAt: new Date().toISOString() };
  if (idx >= 0) all[idx] = next;
  else all.unshift(next);
  writeAll(all);
  return next;
}

export function deleteConversation(id: string) {
  writeAll(readAll().filter((c) => c.id !== id));
}

export function renameConversation(id: string, title: string) {
  const conv = getConversation(id);
  if (!conv) return null;
  return saveConversation({ ...conv, title: title.trim() || "New chat" });
}

export function titleFromFirstMessage(text: string): string {
  const line = text.trim().split(/\n/)[0] ?? "New chat";
  if (line.length <= 48) return line;
  return `${line.slice(0, 45)}…`;
}

export type ConversationGroup = { label: string; items: ChatConversation[] };

export function groupConversationsByRecency(conversations: ChatConversation[]): ConversationGroup[] {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - 7);

  const buckets: Record<string, ChatConversation[]> = {
    Today: [],
    Yesterday: [],
    "Previous 7 days": [],
    Older: [],
  };

  for (const c of conversations) {
    const d = new Date(c.updatedAt);
    if (d >= startOfToday) buckets.Today.push(c);
    else if (d >= startOfYesterday) buckets.Yesterday.push(c);
    else if (d >= startOfWeek) buckets["Previous 7 days"].push(c);
    else buckets.Older.push(c);
  }

  return (["Today", "Yesterday", "Previous 7 days", "Older"] as const)
    .map((label) => ({ label, items: buckets[label] }))
    .filter((g) => g.items.length > 0);
}
