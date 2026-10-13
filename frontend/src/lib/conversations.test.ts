import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createConversation,
  dedupeEmptyConversations,
  deleteConversation,
  findEmptyConversation,
  getConversation,
  listConversations,
  saveConversation,
} from "./conversations";

const STORAGE_KEY = "aqrem_chat_conversations_v1";

function installLocalStorage() {
  const store = new Map<string, string>();
  const ls = {
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => store.clear(),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
  };
  vi.stubGlobal("localStorage", ls);
  return ls;
}

describe("conversations storage", () => {
  beforeEach(() => {
    installLocalStorage();
  });

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY);
  });

  it("deleteConversation removes only the targeted id", () => {
    const a = createConversation(null);
    const b = createConversation(null);
    deleteConversation(a.id);
    expect(listConversations().map((c) => c.id)).toEqual([b.id]);
    expect(getConversation(a.id)).toBeNull();
    expect(getConversation(b.id)).not.toBeNull();
  });

  it("saveConversation does not resurrect a deleted conversation", () => {
    const conv = createConversation(null);
    conv.messages.push({
      id: "m1",
      role: "user",
      content: "hello",
      createdAt: new Date().toISOString(),
    });
    deleteConversation(conv.id);
    expect(getConversation(conv.id)).toBeNull();

    saveConversation(conv);
    expect(listConversations()).toHaveLength(0);
  });

  it("findEmptyConversation and dedupe keep a single empty row", () => {
    createConversation(null);
    createConversation(null);
    createConversation(null);
    expect(listConversations().filter((c) => c.title === "New chat" && c.messages.length === 0).length).toBe(3);
    dedupeEmptyConversations();
    expect(listConversations().filter((c) => c.title === "New chat" && c.messages.length === 0).length).toBe(1);
    expect(findEmptyConversation()).not.toBeNull();
  });

  it("delete leaves sibling conversations intact", () => {
    const a = createConversation(null);
    const b = createConversation(null);
    const c = createConversation(null);
    deleteConversation(b.id);
    expect(listConversations()
      .map((x) => x.id)
      .sort()).toEqual([a.id, c.id].sort());
  });
});
