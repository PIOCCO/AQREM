import { expect, test } from "@playwright/test";
import { join } from "node:path";

const authFile = join(import.meta.dirname, ".auth/employee.json");

test.describe("activity page", () => {
  test.use({ storageState: authFile, viewport: { width: 1440, height: 900 } });

  test("renders header once and toolbar", async ({ page }) => {
    await page.goto("/audit");
    await expect(page.getByRole("heading", { name: "Activity", level: 1 })).toHaveCount(1);
    await expect(page.getByPlaceholder("Search activity")).toBeVisible();
    await expect(page.getByRole("button", { name: "Export" })).toBeVisible();
  });
});
