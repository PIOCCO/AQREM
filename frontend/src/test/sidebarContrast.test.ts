import { describe, expect, it } from "vitest";

function luminance(hex: string): number {
  const raw = hex.replace("#", "");
  const r = parseInt(raw.slice(0, 2), 16) / 255;
  const g = parseInt(raw.slice(2, 4), 16) / 255;
  const b = parseInt(raw.slice(4, 6), 16) / 255;
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(fg: string, bg: string): number {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

/** Dark theme sidebar tokens from index.css html.dark */
const DARK_SIDEBAR = {
  bg: "#2a2a2a",
  fg: "#ececec",
  muted: "#a3a3a3",
};

describe("sidebar nav contrast", () => {
  it("nav text on sidebar background meets 4.5:1 in dark mode", () => {
    expect(contrast(DARK_SIDEBAR.fg, DARK_SIDEBAR.bg)).toBeGreaterThanOrEqual(4.5);
  });

  it("muted nav labels on sidebar background meet 4.5:1 in dark mode", () => {
    expect(contrast(DARK_SIDEBAR.muted, DARK_SIDEBAR.bg)).toBeGreaterThanOrEqual(4.5);
  });
});
