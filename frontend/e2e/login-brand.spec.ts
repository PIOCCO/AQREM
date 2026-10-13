import { expect, test } from "@playwright/test";

test.describe("login brand and theme", () => {
  test.use({ colorScheme: "dark" });

  test("dark login shows real logo and sign-in only", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in to AQREM/i })).toBeVisible();
    await expect(page.getByText("Create account")).toHaveCount(0);
    await expect(page.getByText("Register", { exact: true })).toHaveCount(0);
    const mark = page.locator(".aq-logo-mark img.aq-logo-img--dark").first();
    await expect(mark).toBeVisible();
    await expect(mark).toHaveAttribute("src", /.+/);
    await expect(page.locator("html")).toHaveClass(/dark/);
  });

  test("light login shows black logo variant", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("aqrem_theme", "light");
      document.documentElement.classList.remove("dark");
      document.documentElement.dataset.theme = "light";
    });
    await page.goto("/login");
    const mark = page.locator(".aq-logo-mark img.aq-logo-img--light").first();
    await expect(mark).toBeVisible();
  });
});
