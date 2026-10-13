import { expect, test } from "@playwright/test";

test.describe("Super Admin route guards (anonymous)", () => {
  test("unauthenticated user redirected from super-admin", async ({ page }) => {
    await page.goto("/super-admin/organizations");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });

  test("unauthenticated user redirected from customer admin", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });
});

test.describe("Super Admin route guards (employee session)", () => {
  test.use({ storageState: "e2e/.auth/employee.json" });

  test("employee cannot access super-admin shell", async ({ page }) => {
    await page.goto("/super-admin/organizations");
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });
});
