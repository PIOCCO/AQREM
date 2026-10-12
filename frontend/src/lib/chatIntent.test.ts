import { describe, expect, it } from "vitest";
import { buildConversationalReply, classifyChatIntent } from "./chatIntent";

describe("classifyChatIntent", () => {
  it("detects greeting", () => {
    expect(classifyChatIntent("hi")).toBe("greeting");
    expect(classifyChatIntent("Hello!")).toBe("greeting");
  });

  it("detects thanks", () => {
    expect(classifyChatIntent("Thanks!")).toBe("thanks");
  });

  it("detects help", () => {
    expect(classifyChatIntent("What can you do?")).toBe("help");
  });

  it("returns null for real questions", () => {
    expect(classifyChatIntent("How do we encrypt data at rest?")).toBeNull();
  });
});

describe("buildConversationalReply", () => {
  it("includes starter actions", () => {
    expect(buildConversationalReply("greeting")).toMatch(/questionnaire/i);
  });
});
