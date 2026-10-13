import { expect, test } from "@playwright/test";

/**
 * When PLAYWRIGHT_ONE_PORT_URL is set (e.g. http://127.0.0.1:4173), verifies the
 * same production bundle as FastAPI SERVE_FRONTEND — not Vite preview alone.
 */
test.describe("one-port login surface", () => {
  test.skip(!process.env.PLAYWRIGHT_ONE_PORT_URL, "Set PLAYWRIGHT_ONE_PORT_URL=http://127.0.0.1:4173");

  test("served login is dark sign-in only with real logo", async ({ browser }) => {
    const base = process.env.PLAYWRIGHT_ONE_PORT_URL!.replace(/\/$/, "");
    const context = await browser.newContext({
      baseURL: base,
      colorScheme: "dark",
    });
    const page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem("aqrem_theme", "dark");
      document.documentElement.classList.add("dark");
    });
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in to AQREM/i })).toBeVisible();
    await expect(page.getByText("Create account")).toHaveCount(0);
    await expect(page.getByText("Register", { exact: true })).toHaveCount(0);
    await expect(page.locator(".aq-logo-mark img.aq-logo-img--dark").first()).toBeVisible();
    const html = await page.content();
    expect(html).not.toContain("Create account");
    await page.screenshot({ path: "test-results/one-port-login-dark.png", fullPage: true });
    await context.close();
  });
});
