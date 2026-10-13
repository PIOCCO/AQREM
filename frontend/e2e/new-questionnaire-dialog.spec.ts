import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { join } from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";

const authFile = join(import.meta.dirname, ".auth/employee.json");

const viewports = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1280", width: 1280, height: 720 },
  { name: "mobile-390", width: 390, height: 844 },
] as const;

for (const vp of viewports) {
  test.describe(`new questionnaire dialog ${vp.name} dark`, () => {
    test.use({ storageState: authFile, viewport: { width: vp.width, height: vp.height }, colorScheme: "dark" });

    test("shell, validation, file preview, and a11y", async ({ page }, testInfo) => {
      await page.route("**/api/v1/projects**", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([{ id: "11111111-1111-1111-1111-111111111111", name: "Demo Project" }]),
        });
      });
      await page.route("**/api/v1/questionnaires**", async (route) => {
        if (route.request().method() === "GET") {
          await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
          return;
        }
        await route.continue();
      });
      await page.goto("/questionnaires");
      await page.getByTestId("new-questionnaire-trigger").click();
      const dialog = page.getByTestId("new-questionnaire-dialog");
      await expect(dialog).toBeVisible();

      const box = await dialog.boundingBox();
      expect(box).toBeTruthy();
      if (box) {
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 2);
      }

      await expect(page.locator(".aq-dialog-backdrop")).toBeVisible();
      const backdrop = await page.locator(".aq-dialog-backdrop").evaluate((el) => getComputedStyle(el).backgroundColor);
      expect(backdrop).toMatch(/rgba?\(0,\s*0,\s*0/);

      await expect(page.getByTestId("dialog-confirm")).toBeDisabled();
      await page.getByTestId("qn-name-input").fill("SOC 2 Vendor Review");
      await expect(page.getByTestId("dialog-confirm")).toBeDisabled();

      await page.getByTestId("qn-project-combobox").click();
      const popover = page.getByTestId("qn-project-combobox-popover");
      await expect(popover).toBeVisible({ timeout: 10_000 });
      const firstOpt = popover.getByRole("option").first();
      await expect(firstOpt).toBeVisible();
      await firstOpt.click();
      await expect(page.getByTestId("qn-project-combobox")).not.toContainText("Select project");

      const csvPath = join(import.meta.dirname, "fixtures/sample-questions.csv");
      await page.getByTestId("file-dropzone").click();
      await page.locator("#qn-file").setInputFiles(csvPath);
      await expect(page.getByTestId("qn-file-preview")).toContainText(/Found 2 question/);

      await expect(page.getByLabel("Questionnaire name")).toBeVisible();
      await expect(page.getByTestId("dialog-confirm")).toBeEnabled();

      const axe = await new AxeBuilder({ page }).include('[data-testid="new-questionnaire-dialog"]').analyze();
      expect(axe.violations.filter((v) => v.impact === "critical")).toEqual([]);

      if (vp.name === "desktop-1440") {
        await page.screenshot({ path: join(testInfo.outputDir, "dialog-filled-dark.png"), fullPage: false });
      }
    });
  });
}

test.describe("new questionnaire dialog light", () => {
  test.use({ storageState: authFile, viewport: { width: 1440, height: 900 }, colorScheme: "light" });

  test("wrong file type shows error", async ({ page }) => {
    await page.goto("/questionnaires");
    await page.getByTestId("new-questionnaire-trigger").click();
    const txt = join(import.meta.dirname, ".tmp-bad.txt");
    writeFileSync(txt, "not a questionnaire");
    await page.locator("#qn-file").setInputFiles(txt);
    await expect(page.getByRole("alert").filter({ hasText: /CSV or XLSX/i })).toBeVisible();
  });
});
