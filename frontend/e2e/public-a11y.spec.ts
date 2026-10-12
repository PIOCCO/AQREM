import { expect, test } from "@playwright/test";

test.describe("public routes", () => {
  test("login page buttons and links are named and actionable", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();

    const buttons = page.locator("button");
    const count = await buttons.count();
    for (let i = 0; i < count; i++) {
      const btn = buttons.nth(i);
      const name = (await btn.getAttribute("aria-label")) || (await btn.innerText()).trim();
      expect(name.length, `button #${i} accessible name`).toBeGreaterThan(0);
      const disabled = await btn.isDisabled();
      if (!disabled) {
        await expect(btn).toBeEnabled();
      }
    }
  });

  test("theme script defaults html to dark before hydration", async ({ page }) => {
    await page.goto("/login");
    const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(theme).toBe("dark");
  });

  test("focus-visible ring on login submit control", async ({ page }) => {
    await page.goto("/login");
    await page.keyboard.press("Tab");
    const focused = page.locator(":focus-visible");
    await expect(focused.first()).toBeVisible();
  });
});
