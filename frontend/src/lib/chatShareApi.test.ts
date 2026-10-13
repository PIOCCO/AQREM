import { describe, expect, it } from "vitest";
import { conversationToSharePayload, shareUrlFromPath } from "./chatShareApi";
import type { ChatConversation } from "./conversations";

describe("chatShareApi", () => {
  it("builds absolute share URLs from API paths", () => {
    const prev = globalThis.window;
    // @ts-expect-error test shim
    globalThis.window = { location: { origin: "https://app.example.com" } };
    expect(shareUrlFromPath("/share/abc123")).toBe("https://app.example.com/share/abc123");
    globalThis.window = prev;
  });

  it("maps conversation messages without client-only meta", () => {
    const conv: ChatConversation = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "Review",
      projectId: null,
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      messages: [
        {
          id: "m1",
          role: "user",
          content: "Hi",
          createdAt: "2026-01-01T00:01:00Z",
          meta: { citations: [{ evidenceId: "e1", filePath: "x", excerpt: "y" }] },
        },
      ],
    };
    const payload = conversationToSharePayload(conv);
    expect(payload.client_conversation_id).toBe(conv.id);
    expect(payload.messages[0]).toEqual({
      role: "user",
      content: "Hi",
      created_at: "2026-01-01T00:01:00Z",
    });
    expect(payload.messages[0]).not.toHaveProperty("meta");
  });
});
