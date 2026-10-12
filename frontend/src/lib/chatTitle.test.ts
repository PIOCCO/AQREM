import { describe, expect, it } from "vitest";
import { conversationTitleAfterUserMessage, titleFromFirstMessage } from "./chatTitle";

describe("titleFromFirstMessage", () => {
  it("truncates long lines", () => {
    const long = "a".repeat(60);
    expect(titleFromFirstMessage(long).endsWith("…")).toBe(true);
  });
});

describe("conversationTitleAfterUserMessage", () => {
  it("keeps New chat for greetings", () => {
    expect(conversationTitleAfterUserMessage("New chat", "hi")).toBe("New chat");
  });

  it("generates title for real questions", () => {
    expect(conversationTitleAfterUserMessage("New chat", "SOC 2 encryption controls")).toBe(
      "SOC 2 encryption controls",
    );
  });
});
