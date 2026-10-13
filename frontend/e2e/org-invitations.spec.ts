import { test, expect } from "@playwright/test";

test.describe("public join surface", () => {
  test("join page uses dark auth shell without token", async ({ page }) => {
    await page.goto("/join");
    await expect(page.getByRole("heading", { name: /join/i })).toBeVisible();
    await expect(page.locator(".aq-card")).toBeVisible();
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).not.toBe("rgb(255, 255, 255)");
  });

  test("accept invite strips token from URL", async ({ page }) => {
    await page.goto("/accept-invite?token=abc123secret");
    await expect(page).toHaveURL(/\/accept-invite$/);
  });
});
