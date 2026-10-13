import { expect, test } from "@playwright/test";

test("platform console shows org metadata only, not tenant documents", async ({ page }) => {
  const email = process.env.QA_PLATFORM_EMAIL ?? "qa-platform@audit.example";
  const password = process.env.QA_PLATFORM_PASSWORD;
  test.skip(!password, "Set QA_PLATFORM_PASSWORD to run platform UI privacy check");

  await page.goto("/login");
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: /^Sign in$/i }).click();
  await expect(page).toHaveURL(/super-admin/, { timeout: 20_000 });

  await expect(page.getByRole("heading", { name: /Platform administration/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("body")).not.toContainText("Evidence preview");
  await expect(page.locator("body")).not.toContainText("Questionnaire");
  await page.screenshot({ path: "test-results/platform-admin-console.png", fullPage: true });
});
