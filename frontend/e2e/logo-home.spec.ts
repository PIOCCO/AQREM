import { expect, test } from "@playwright/test";
import { join } from "node:path";

const authFile = join(import.meta.dirname, ".auth/employee.json");

test.describe("AQREM logo home", () => {
  test.use({ storageState: authFile, viewport: { width: 1440, height: 900 } });

  test("logo navigates home without creating conversations", async ({ page, context }) => {
    await page.goto("/settings");
    const before = await page.getByTestId("chat-sidebar").locator(".ref-conv-item").count();
    await page.getByTestId("logo-home-link").click();
    await expect(page).toHaveURL(/\/(\?.*)?$/);
    await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
    const after = await page.getByTestId("chat-sidebar").locator(".ref-conv-item").count();
    expect(after).toBe(before);

    await page.getByTestId("logo-home-link").click();
    await expect(page).toHaveURL(/\/(\?.*)?$/);

    const mod = process.platform === "darwin" ? "Meta" : "Control";
    const [newPage] = await Promise.all([
      context.waitForEvent("page"),
      page.getByTestId("logo-home-link").click({ modifiers: [mod] }),
    ]);
    await newPage.waitForLoadState();
    await expect(newPage).toHaveURL(/\/(\?.*)?$/);
    await newPage.close();
  });

  test("logo image loads and placeholder green A is gone", async ({ page }) => {
    await page.goto("/");
    const link = page.getByTestId("logo-home-link");
    await expect(link).toHaveAttribute("aria-label", "AQREM home");
    await expect(link.locator(".aq-logo-img--dark")).toBeVisible();
    await expect(link.locator('div.rounded-md:has-text("A")')).toHaveCount(0);
    const resp = await page.request.get("/favicon.ico");
    expect(resp.status()).toBe(200);
  });

  test("collapsed sidebar keeps logo link", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("sidebar-toggle").click();
    await expect(page.getByTestId("logo-home-link")).toBeVisible();
    await page.getByTestId("logo-home-link").click();
    await expect(page).toHaveURL(/\/(\?.*)?$/);
  });
});

test.describe("login logo", () => {
  test("mark visible on login", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator(".aq-logo-mark .aq-logo-img--dark")).toBeVisible();
    await expect(page.getByText("Sign in to AQREM")).toBeVisible();
  });
});
