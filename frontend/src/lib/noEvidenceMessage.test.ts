import { describe, expect, it } from "vitest";
import { formatNoEvidenceMessage } from "./noEvidenceMessage";

describe("formatNoEvidenceMessage", () => {
  it("includes project and source count", () => {
    const msg = formatNoEvidenceMessage("Demo Project", 2);
    expect(msg).toContain("Demo Project");
    expect(msg).toContain("2 sources searched");
    expect(msg.toLowerCase()).not.toContain("indexed");
  });
});
