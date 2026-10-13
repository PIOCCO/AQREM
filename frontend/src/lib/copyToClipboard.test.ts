import { afterEach, describe, expect, it, vi } from "vitest";
import { copyToClipboard } from "./copyToClipboard";

describe("copyToClipboard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses navigator.clipboard when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const result = await copyToClipboard("https://example.com/share/tok");
    expect(result).toEqual({ ok: true });
    expect(writeText).toHaveBeenCalledWith("https://example.com/share/tok");
  });

  it("returns error when clipboard fails and fallback fails", async () => {
    vi.stubGlobal("navigator", {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    vi.stubGlobal("document", {
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
      createElement: () => ({
        style: {},
        setAttribute: vi.fn(),
        select: vi.fn(),
        value: "",
      }),
      execCommand: () => false,
    });
    const result = await copyToClipboard("x");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("denied");
  });
});
