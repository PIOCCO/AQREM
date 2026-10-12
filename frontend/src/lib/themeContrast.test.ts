import { describe, expect, it } from "vitest";

/** WCAG relative luminance (sRGB). */
function luminance(hex: string): number {
  const raw = hex.replace("#", "");
  const r = parseInt(raw.slice(0, 2), 16) / 255;
  const g = parseInt(raw.slice(2, 4), 16) / 255;
  const b = parseInt(raw.slice(4, 6), 16) / 255;
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: string, b: string): number {
  const l1 = luminance(a);
  const l2 = luminance(b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

const DARK = {
  background: "#141414",
  surface: "#1f1f1f",
  textPrimary: "#ececec",
  textMuted: "#a3a3a3",
};

const LIGHT = {
  background: "#f5f5f4",
  surface: "#ffffff",
  textPrimary: "#171717",
  textMuted: "#737373",
};

describe("theme contrast tokens", () => {
  it("dark mode primary text on background meets 4.5:1", () => {
    expect(contrast(DARK.textPrimary, DARK.background)).toBeGreaterThanOrEqual(4.5);
  });

  it("dark mode primary text on surface meets 4.5:1", () => {
    expect(contrast(DARK.textPrimary, DARK.surface)).toBeGreaterThanOrEqual(4.5);
  });

  it("dark mode muted text on surface meets 4.5:1", () => {
    expect(contrast(DARK.textMuted, DARK.surface)).toBeGreaterThanOrEqual(4.5);
  });

  it("light mode primary text on surface meets 4.5:1", () => {
    expect(contrast(LIGHT.textPrimary, LIGHT.surface)).toBeGreaterThanOrEqual(4.5);
  });

  it("light mode muted text on surface meets 4.5:1", () => {
    expect(contrast(LIGHT.textMuted, LIGHT.surface)).toBeGreaterThanOrEqual(4.5);
  });
});
