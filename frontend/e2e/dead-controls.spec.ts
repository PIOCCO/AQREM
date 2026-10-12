import { expect, test } from "@playwright/test";

test("login shell controls have accessible names", async ({ page }) => {
  await page.goto("/login");
  const issues = await page.evaluate(() => {
    const out: string[] = [];
    document.querySelectorAll("button").forEach((btn) => {
      if (btn.disabled) return;
      const name = btn.getAttribute("aria-label") || btn.textContent?.trim() || "";
      if (!name) out.push("button missing accessible name");
    });
    document.querySelectorAll("a[href]").forEach((a) => {
      const name = a.getAttribute("aria-label") || a.textContent?.trim() || "";
      if (!name) out.push(`link missing name: ${a.getAttribute("href")}`);
    });
    return out;
  });
  expect(issues).toEqual([]);
});
