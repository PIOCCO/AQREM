import { expect, test } from "@playwright/test";
import { join } from "node:path";

test.describe("chat sidebar visibility", () => {
  test.use({ storageState: join(import.meta.dirname, ".auth/employee.json") });

  test("sidebar is visible on desktop chat", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    const sidebar = page.locator("aside.chat-sidebar");
    await expect(sidebar).toBeVisible();
    const box = await sidebar.boundingBox();
    expect(box?.width ?? 0).toBeGreaterThan(200);
    await expect(page.locator(".ref-nav-item").first()).toBeVisible();
  });
});
