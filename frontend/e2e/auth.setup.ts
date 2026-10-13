import { test as setup, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const credPath = join(import.meta.dirname, ".qa-credentials.json");

setup("employee session", async ({ page }) => {
  const cred = JSON.parse(readFileSync(credPath, "utf8")) as {
    employee_token: string;
    organization_id: string;
  };
  await page.goto("/login");
  await page.evaluate(
    ({ token, org }) => {
      localStorage.setItem("aqrem_token", token);
      localStorage.setItem("aqrem_org", org);
      localStorage.setItem("aqrem_theme", "dark");
      document.documentElement.classList.add("dark");
      document.documentElement.dataset.theme = "dark";
    },
    { token: cred.employee_token, org: cred.organization_id },
  );
  await page.goto("/dashboard");
  await expect(page.locator("main")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/Good (morning|afternoon|evening)/i)).toBeVisible({ timeout: 15_000 });
  await page.context().storageState({ path: join(import.meta.dirname, ".auth/employee.json") });
});
