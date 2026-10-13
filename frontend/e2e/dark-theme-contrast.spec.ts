import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const LIGHT_BG_THRESHOLD = 0.4;

function parseRgb(color: string): [number, number, number] | null {
  const m = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return null;
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

function relativeLuminance(r: number, g: number, b: number): number {
  const s = [r, g, b].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * s[0]! + 0.7152 * s[1]! + 0.0722 * s[2]!;
}

async function assertDarkSurfaces(page: import("@playwright/test").Page) {
  await page.evaluate(async (threshold) => {
    const allow = new Set(["IMG", "SVG", "VIDEO", "CANVAS"]);
    const offenders: string[] = [];
    const nodes = document.querySelectorAll("body *");
    for (const el of nodes) {
      if (!(el instanceof HTMLElement)) continue;
      if (allow.has(el.tagName)) continue;
      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") continue;
      const rect = el.getBoundingClientRect();
      if (rect.width < 4 || rect.height < 4) continue;
      const bg = style.backgroundColor;
      const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (!m) continue;
      const r = Number(m[1]);
      const g = Number(m[2]);
      const b = Number(m[3]);
      const a = bg.includes("rgba") ? Number(bg.split(",").pop()?.replace(/[^0-9.]/g, "") ?? 1) : 1;
      if (a < 0.05) continue;
      const lum =
        0.2126 * (r / 255) ** 2.2 + 0.7152 * (g / 255) ** 2.2 + 0.0722 * (b / 255) ** 2.2;
      if (lum > threshold) {
        offenders.push(`${el.tagName}.${el.className} bg=${bg}`);
      }
      if (offenders.length > 12) break;
    }
    if (offenders.length) {
      throw new Error(`Light backgrounds in dark mode:\n${offenders.join("\n")}`);
    }
  }, LIGHT_BG_THRESHOLD);
}

test.describe("dark theme — platform admin", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("aqrem_theme", "dark");
      document.documentElement.classList.add("dark");
      document.documentElement.dataset.theme = "dark";
    });
  });

  test("super-admin has dark canvas and passes axe", async ({ page }) => {
    const password = process.env.QA_PLATFORM_PASSWORD ?? process.env.E2E_PLATFORM_PASSWORD;
    test.skip(!password, "Set QA_PLATFORM_PASSWORD for platform dark-theme check");
    const email = process.env.QA_PLATFORM_EMAIL ?? process.env.E2E_PLATFORM_EMAIL ?? "qa-platform@audit.example";

    await page.goto("/login");
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password!);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/super-admin/, { timeout: 30_000 });

    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const rgb = parseRgb(bg);
    expect(rgb).not.toBeNull();
    if (rgb) {
      expect(relativeLuminance(rgb[0], rgb[1], rgb[2])).toBeLessThan(0.25);
    }

    await assertDarkSurfaces(page);

    const results = await new AxeBuilder({ page }).withTags(["wcag2aa", "wcag21aa"]).analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);

    await page.screenshot({ path: "test-results/dark-master-admin.png", fullPage: true });
  });
});
