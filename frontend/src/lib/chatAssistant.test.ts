import { describe, expect, it, vi, beforeEach } from "vitest";
import * as api from "./api";
import { generateAssistantReply } from "./chatAssistant";

describe("generateAssistantReply", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("does not call askChat for greetings", async () => {
    const ask = vi.spyOn(api, "askChat");
    const session = { token: "t", organizationId: "org" };
    const reply = await generateAssistantReply(session, "hello", "proj-1");
    expect(ask).not.toHaveBeenCalled();
    expect(reply.meta.conversational).toBe(true);
    expect(reply.meta.insufficientEvidence).toBeUndefined();
    expect(reply.skippedRetrieval).toBe(true);
  });

  it("marks insufficient evidence from API", async () => {
    vi.spyOn(api, "askChat").mockResolvedValue({
      answer: "I couldn't find evidence for that in **P** (0 sources searched). Try rephrasing, or add the document that covers it.",
      evidence_sufficiency: "insufficient",
      outcome: "insufficient_evidence",
      is_draft: true,
      citations: [],
      sources_searched: 0,
      project_name: "P",
    });
    const session = { token: "t", organizationId: "org" };
    const reply = await generateAssistantReply(session, "What is our DR policy?", "proj-1");
    expect(reply.meta.insufficientEvidence).toBe(true);
    expect(reply.meta.conversational).toBeFalsy();
  });

  it("keeps the two empty-document messages distinct", async () => {
    const session = { token: "t", organizationId: "org" };
    vi.spyOn(api, "askChat").mockResolvedValueOnce({
      answer: "No documents available",
      evidence_sufficiency: "insufficient",
      outcome: "insufficient_evidence",
      is_draft: true,
      citations: [],
    });
    const none = await generateAssistantReply(session, "What is our DR policy?", null);
    expect(none.content).toBe("No documents available");
    expect(none.content.toLowerCase()).not.toContain("company documents");

    vi.spyOn(api, "askChat").mockResolvedValueOnce({
      answer: "I couldn't find this in the company documents",
      evidence_sufficiency: "insufficient",
      outcome: "insufficient_evidence",
      is_draft: true,
      citations: [],
    });
    const miss = await generateAssistantReply(session, "What is our DR policy?", null);
    expect(miss.content).toBe("I couldn't find this in the company documents");
    expect(miss.content).not.toContain("No documents available");
  });
});
