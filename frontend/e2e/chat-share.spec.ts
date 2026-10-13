import { expect, test } from "@playwright/test";
import { join } from "node:path";

const authFile = join(import.meta.dirname, ".auth/employee.json");

test.describe("chat share dialog", () => {
  test.use({ storageState: authFile, viewport: { width: 1280, height: 800 } });

  test("Share opens dialog with link and copy feedback", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 20_000 });
    const composer = page.getByRole("textbox", { name: "Message" });
    await composer.fill("Share flow test");
    await page.getByRole("button", { name: "Send message" }).click();
    await page.waitForURL(/\/c\//, { timeout: 15_000 });
    await page.getByRole("button", { name: "Share" }).click();
    await expect(page.getByRole("dialog", { name: "Share conversation" })).toBeVisible();
    const input = page.getByRole("textbox", { name: "Shareable link" });
    await expect(input).toHaveValue(/\/share\//, { timeout: 15_000 });
    await page.getByRole("button", { name: "Copy link" }).click();
    await expect(page.getByRole("button", { name: "Copied!" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Share conversation" })).not.toBeVisible();
  });
});
