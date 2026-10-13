import { expect, test } from "@playwright/test";
import { join } from "node:path";

function luminance([r, g, b]: [number, number, number]) {
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function parseRgb(css: string): [number, number, number] | null {
  const m = css.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return null;
  return [Number(m[1]) / 255, Number(m[2]) / 255, Number(m[3]) / 255];
}

function contrastRatio(fg: string, bg: string): number | null {
  const f = parseRgb(fg);
  const b = parseRgb(bg);
  if (!f || !b) return null;
  const l1 = luminance(f);
  const l2 = luminance(b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

test.describe("dark mode contrast (computed styles)", () => {
  test.use({ storageState: join(import.meta.dirname, ".auth/employee.json") });

  test("dashboard primary controls", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("main .ref-metric-card").first()).toBeVisible({ timeout: 20_000 });
    await expect
      .poll(async () =>
        page.evaluate(() => {
          const card = document.querySelector("main .ref-metric-card");
          if (!card) return "missing";
          return getComputedStyle(card).backgroundColor;
        }),
      )
      .not.toBe("rgb(255, 255, 255)");
    const ratios = await page.evaluate(() => {
      function parse(css: string) {
        const m = css.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
      }
      function lum([r, g, b]: number[]) {
        const f = (c: number) => {
          const x = c / 255;
          return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
        };
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
      }
      function cr(fg: string, bg: string) {
        const f = parse(fg);
        const b = parse(bg);
        if (!f || !b) return 0;
        const l1 = lum(f);
        const l2 = lum(b);
        return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      }
      const card = document.querySelector("main .ref-metric-card");
      const label = document.querySelector("main .ref-metric-label");
      const btn = document.querySelector("main .aq-btn-secondary");
      if (!card || !label || !btn) return null;
      const cardBg = getComputedStyle(card).backgroundColor;
      const labelFg = getComputedStyle(label).color;
      const btnBg = getComputedStyle(btn).backgroundColor;
      const btnFg = getComputedStyle(btn).color;
      const html = getComputedStyle(document.documentElement);
      return {
        label: cr(labelFg, cardBg),
        btn: cr(btnFg, btnBg),
        cardBg,
        labelFg,
        surfaceVar: html.getPropertyValue("--color-surface").trim(),
        dark: document.documentElement.classList.contains("dark"),
      };
    });
    expect(ratios).not.toBeNull();
    expect(ratios!.label, JSON.stringify(ratios)).toBeGreaterThanOrEqual(4.5);
    expect(ratios!.btn, JSON.stringify(ratios)).toBeGreaterThanOrEqual(4.5);
  });
});
