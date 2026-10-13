import { test as setup, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const credPath = join(import.meta.dirname, ".qa-credentials.json");

setup("employee session", async ({ page }) => {
  const cred = JSON.parse(readFileSync(credPath, "utf8")) as {
    employee_email: string;
    employee_password: string;
  };
  await page.goto("/login");
  await page.getByPlaceholder("Email").fill(cred.employee_email);
  await page.getByPlaceholder("Password").fill(cred.employee_password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.locator("aside.chat-sidebar")).toBeVisible({ timeout: 20_000 });
  await page.context().storageState({ path: join(import.meta.dirname, ".auth/employee.json") });
});
