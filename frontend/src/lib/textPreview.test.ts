import { describe, expect, it } from "vitest";
import { capEvidenceListContent, splitLinesLimited } from "./textPreview";

describe("capEvidenceListContent", () => {
  it("caps oversized list payloads", () => {
    const { text, truncated } = capEvidenceListContent("x".repeat(5000), 2000);
    expect(text.length).toBe(2001);
    expect(truncated).toBe(true);
  });
});

describe("splitLinesLimited", () => {
  it("does not split the entire string when line count exceeds max", () => {
    const manyLines = `${"a\n".repeat(10_000)}tail`;
    const { lines, truncated } = splitLinesLimited(manyLines, 100, 50_000);
    expect(lines.length).toBe(100);
    expect(truncated).toBe(true);
  });
});
