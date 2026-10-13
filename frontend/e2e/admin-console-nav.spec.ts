import { expect, test } from "@playwright/test";
import { join } from "node:path";

const authFile = join(import.meta.dirname, ".auth/employee.json");

function mockTenantMe(page: import("@playwright/test").Page, permissions: string[], role: string) {
  return page.route("**/api/v1/auth/me/tenant", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "employee@example.com",
        full_name: "Test User",
        organization_id: "org-1",
        role,
        is_platform_admin: false,
        must_change_password: false,
        permissions,
      }),
    });
  });
}

function mockAuthMe(page: import("@playwright/test").Page, permissions: string[], role: string) {
  return page.route("**/api/v1/auth/me", async (route) => {
    if (route.request().url().includes("/tenant")) {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "user-1",
        email: "employee@example.com",
        full_name: "Test User",
        organization_id: "org-1",
        role,
        is_platform_admin: false,
        must_change_password: false,
        permissions,
      }),
    });
  });
}

test.describe("admin console nav", () => {
  test.use({ storageState: authFile, viewport: { width: 1440, height: 900 } });

  test("employee does not see admin console in DOM", async ({ page }) => {
    await mockAuthMe(page, [], "EDITOR");
    await mockTenantMe(page, [], "EDITOR");
    await page.goto("/settings");
    await expect(page.getByTestId("admin-console-link")).toHaveCount(0);
    await expect(page.getByTestId("admin-console-link-rail")).toHaveCount(0);
  });

  test("org admin sees link and can open admin", async ({ page }) => {
    await mockAuthMe(page, ["admin_console:access"], "ORG_ADMIN");
    await mockTenantMe(page, ["admin_console:access"], "ORG_ADMIN");
    await page.route("**/api/v1/org-admin/console-enter**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' });
    });
    await page.route("**/api/v1/org-admin/overview**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          organization: { id: "1", name: "Demo", license_limit: 5, license_status: "active" },
          setup: {
            steps: [],
            completed_count: 0,
            total_count: 0,
            incomplete_count: 0,
            percent: 0,
            employee_link_enabled: true,
            storage_configured: true,
            model_token_status: "ok",
          },
          seats: { used: 1, limit: 5, available: 4, is_full: false },
          employee_link: { url_path: "/login", enabled: true },
        }),
      });
    });
    await page.goto("/settings");
    await expect(page.getByTestId("admin-console-link")).toBeVisible();
    await page.getByTestId("admin-console-link").click();
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByText("Back to assistant")).toBeVisible();
  });

  test("org admin data storage page loads with keyboard nav", async ({ page }) => {
    await mockAuthMe(page, ["admin_console:access"], "ORG_ADMIN");
    await mockTenantMe(page, ["admin_console:access"], "ORG_ADMIN");
    await page.route("**/api/v1/org-admin/console-enter**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' });
    });
    await page.route("**/api/v1/org-admin/data-storage**", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            storage_mode: "managed_colocated",
            connection_method: "managed",
            status: "active",
            host: null,
            port: null,
            database_name: null,
            schema_name: "public",
            ssl_mode: "verify-full",
            username: null,
            has_credentials: false,
            schema_version: 1,
            last_health_status: "healthy",
            last_health_summary: "Managed storage",
            last_latency_ms: null,
            last_health_check_at: null,
            paused: false,
          }),
        });
        return;
      }
      await route.fallback();
    });
    await page.goto("/admin/data-storage");
    await expect(page.getByRole("heading", { name: "Data storage" })).toBeVisible();
    await expect(page.getByRole("radio", { name: /Managed by AQREM/i })).toBeFocused({ timeout: 5000 }).catch(() => {});
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: /Save storage settings/i })).toBeVisible();
  });

  test("employee direct /admin shows access denied", async ({ page }) => {
    await mockAuthMe(page, [], "EDITOR");
    await mockTenantMe(page, [], "EDITOR");
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: /don't have access/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /assistant/i })).toBeVisible();
  });
});
