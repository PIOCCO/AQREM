import { classifyChatIntent } from "./chatIntent";

export function titleFromFirstMessage(text: string): string {
  const line = text.trim().split(/\n/)[0] ?? "New chat";
  if (line.length <= 48) return line;
  return `${line.slice(0, 45)}…`;
}

/** Returns a new title when the first real question arrives; null keeps "New chat". */
export function conversationTitleAfterUserMessage(currentTitle: string, text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return currentTitle;
  if (classifyChatIntent(trimmed)) return currentTitle;
  if (currentTitle !== "New chat") return currentTitle;
  return titleFromFirstMessage(trimmed);
}
