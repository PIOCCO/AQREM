import { expect, test } from "@playwright/test";

test.describe("login without public registration", () => {
  test("register URLs redirect to sign-in without register UI", async ({ page }) => {
    await page.goto("/register");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: /Sign in to AQREM/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Sign in$/i })).toBeVisible();
    await expect(page.getByText("Create account")).toHaveCount(0);
    await expect(page.getByText("Register", { exact: true })).toHaveCount(0);
  });

  test("login?mode=register strips mode and shows sign-in", async ({ page }) => {
    await page.goto("/login?mode=register");
    await page.waitForURL((url) => url.pathname === "/login" && !url.searchParams.has("mode"));
    await expect(page.getByRole("heading", { name: /Sign in to AQREM/i })).toBeVisible();
  });

  test("registration API returns 404", async ({ request }) => {
    const res = await request.post("/api/v1/auth/register", {
      data: { email: "nobody@example.com", password: "not-a-real-password" },
    });
    expect(res.status()).toBe(404);
  });

  test("accept invitation page still loads", async ({ page }) => {
    await page.goto("/accept-invite?token=test-token");
    await expect(page.getByRole("heading", { name: /Set your password/i })).toBeVisible();
  });
});
