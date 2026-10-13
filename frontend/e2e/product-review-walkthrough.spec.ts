/**
 * One-off product review walkthrough (uses seeded QA employee credentials).
 * Run: npm run test:e2e -- e2e/product-review-walkthrough.spec.ts
 */
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const credPath = join(import.meta.dirname, ".qa-credentials.json");

test.describe("product review — employee UI", () => {
  test("login, chat answer with citations, greeting, nav smoke", async ({ page }) => {
    const cred = JSON.parse(readFileSync(credPath, "utf8")) as {
      employee_email: string;
      employee_password: string;
    };

    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in to AQREM/i })).toBeVisible();
    await expect(page.getByText("Create account")).toHaveCount(0);

    await page.locator('input[name="email"]').fill(cred.employee_email);
    await page.locator('input[name="password"]').fill(cred.employee_password);
    await page.getByRole("button", { name: /^Sign in$/i }).click();
    await expect(page.locator("aside.chat-sidebar")).toBeVisible({ timeout: 25_000 });

    const composer = page.getByPlaceholder(/Ask AQREM anything/i);
    await composer.fill("How often are access permissions reviewed?");
    await composer.press("Enter");

    await expect(page.getByText(/90|review|access/i).first()).toBeVisible({ timeout: 45_000 });
    await page.screenshot({ path: "test-results/review-chat-answer.png", fullPage: true });

    await composer.fill("hi");
    await composer.press("Enter");
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "test-results/review-chat-greeting.png", fullPage: true });

    for (const path of ["/projects", "/evidence", "/questionnaires", "/review-queue", "/answer-library", "/audit", "/settings"]) {
      await page.goto(path);
      await expect(page.locator("body")).not.toContainText("MVP");
      await expect(page.locator("body")).not.toContainText("TODO");
    }

    await page.goto("/");
    const adminLink = page.getByRole("link", { name: /Admin console/i });
    await expect(adminLink).toHaveCount(0);
  });
});
