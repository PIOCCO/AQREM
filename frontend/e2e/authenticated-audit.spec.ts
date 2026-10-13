import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { join } from "node:path";

const ROUTES: { path: string; name: string }[] = [
  { path: "/", name: "chat" },
  { path: "/dashboard", name: "dashboard" },
  { path: "/projects", name: "projects" },
  { path: "/sources", name: "sources" },
  { path: "/evidence", name: "evidence" },
  { path: "/questionnaires", name: "questionnaires" },
  { path: "/review-queue", name: "review-queue" },
  { path: "/answer-library", name: "answer-library" },
  { path: "/audit", name: "activity" },
  { path: "/settings", name: "settings" },
];

const shotDir = process.env.QA_SCREENSHOT_DIR || join(import.meta.dirname, "screenshots");

test.describe("authenticated UX audit (employee)", () => {
  test.use({ storageState: join(import.meta.dirname, ".auth/employee.json") });

  for (const { path, name } of ROUTES) {
    test(`${name} loads without critical a11y violations`, async ({ page }, testInfo) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      await page.goto(path);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("main")).toBeVisible({ timeout: 20_000 });
      if (path !== "/") {
        await page.waitForTimeout(500);
      }
      const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
      expect(theme, "dark mode default").toBe("dark");

      await page.screenshot({ path: join(shotDir, `${name}-dark.png`), fullPage: true });

      const results = await new AxeBuilder({ page })
        .include("main")
        .disableRules(["color-contrast"])
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      if (serious.length) {
        await testInfo.attach("axe-serious", {
          body: JSON.stringify(serious, null, 2),
          contentType: "application/json",
        });
      }
      expect(serious, `axe on ${path}`).toEqual([]);

      const horizontalScroll = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2,
      );
      expect(horizontalScroll, "no horizontal scroll at default viewport").toBe(false);

      expect(consoleErrors.filter((e) => !e.includes("favicon")), `console errors on ${path}`).toEqual([]);
    });
  }

  test("settings light theme toggle", async ({ page }) => {
    await page.goto("/settings");
    const light = page.getByRole("radio", { name: /light/i });
    const dark = page.getByRole("radio", { name: /dark/i });
    if (await light.isVisible()) {
      await light.click();
      await expect.poll(async () => page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe(
        "light",
      );
      await page.screenshot({ path: join(shotDir, "settings-light.png"), fullPage: true });
      await dark.click();
      await expect.poll(async () => page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe(
        "dark",
      );
    }
  });
});
