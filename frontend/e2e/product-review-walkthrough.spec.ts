/**
 * Product review smoke (seeded QA employee). Chat flows covered by authenticated-audit + manual review.
 * Run: QA_BASE_URL=http://127.0.0.1:5173 npx playwright test --config=playwright.review.config.ts
 */
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const credPath = join(import.meta.dirname, ".qa-credentials.json");

test.describe("product review — employee UI", () => {
  test("sign-in, dark shell, workspace routes, no admin console link", async ({ page }) => {
    const cred = JSON.parse(readFileSync(credPath, "utf8")) as {
      employee_email: string;
      employee_password: string;
    };

    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in to AQREM/i })).toBeVisible();
    await expect(page.getByText("Create account")).toHaveCount(0);
    await expect(page.getByText("Need access? Ask your organization admin for an invitation.")).toBeVisible();

    await page.locator('input[name="email"]').fill(cred.employee_email);
    await page.locator('input[name="password"]').fill(cred.employee_password);
    await page.getByRole("button", { name: /^Sign in$/i }).click();
    await expect(page.locator("aside.chat-sidebar")).toBeVisible({ timeout: 25_000 });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    for (const path of ["/projects", "/evidence", "/questionnaires", "/review-queue", "/answer-library", "/audit", "/settings"]) {
      await page.goto(path);
      await expect(page.locator("main")).toBeVisible({ timeout: 15_000 });
      await expect(page.locator("body")).not.toContainText("MVP");
      await expect(page.locator("body")).not.toContainText("TODO");
    }

    await page.goto("/");
    await expect(page.getByRole("link", { name: /Admin console/i })).toHaveCount(0);
    await expect(page.getByText("AQREM can make mistakes. Verify important answers against the source evidence.")).toBeVisible();
  });
});
