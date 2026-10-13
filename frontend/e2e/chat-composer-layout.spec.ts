import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { mkdirSync } from "node:fs";

const authFile = join(import.meta.dirname, ".auth/employee.json");
const SHOT_DIR = join(import.meta.dirname, "../../artifacts/composer-screenshots");

const VIEWPORTS = [
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
] as const;

async function openChat(page: Page, theme: "dark" | "light", sidebarCollapsed: boolean) {
  await page.addInitScript(
    ({ themeKey, themeValue, sidebarKey, collapsed }) => {
      localStorage.setItem(themeKey, themeValue);
      localStorage.setItem(sidebarKey, collapsed ? "1" : "0");
    },
    {
      themeKey: "aqrem_theme",
      themeValue: theme,
      sidebarKey: "aqrem_sidebar_collapsed",
      collapsed: sidebarCollapsed,
    },
  );
  await page.goto("/");
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 20_000 });
  await expect.poll(async () => page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe(theme);
}

async function mainAreaBox(page: Page) {
  return page.locator(".app-main").boundingBox();
}

async function columnBox(page: Page, testId: string) {
  return page.getByTestId(testId).boundingBox();
}

async function assertNoHorizontalPageScroll(page: Page) {
  const metrics = await page.evaluate(() => ({
    doc: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    body: document.body.scrollWidth <= document.body.clientWidth + 1,
  }));
  expect(metrics.doc).toBe(true);
  expect(metrics.body).toBe(true);
}

async function assertComposerInViewport(page: Page) {
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  const shell = await page.getByTestId("chat-composer-shell").boundingBox();
  const send = await page.getByTestId("chat-composer-send").boundingBox();
  expect(shell).not.toBeNull();
  expect(send).not.toBeNull();
  if (shell && send && viewport) {
    expect(shell.x).toBeGreaterThanOrEqual(0);
    expect(shell.y).toBeGreaterThanOrEqual(0);
    expect(shell.x + shell.width).toBeLessThanOrEqual(viewport.width + 1);
    expect(shell.y + shell.height).toBeLessThanOrEqual(viewport.height + 1);
    expect(send.x + send.width).toBeLessThanOrEqual(viewport.width + 1);
  }
}

async function assertColumnAlignment(page: Page) {
  const messages = page.getByTestId("chat-messages-column");
  const contentCol = (await messages.isVisible())
    ? await messages.boundingBox()
    : await page.getByTestId("chat-scroll-column").boundingBox();
  const composerCol = await page.getByTestId("chat-composer-column").boundingBox();
  const scope = await page.getByRole("button", { name: /Scope:/ }).boundingBox();
  expect(contentCol).not.toBeNull();
  expect(composerCol).not.toBeNull();
  expect(scope).not.toBeNull();
  if (contentCol && composerCol && scope) {
    expect(Math.abs(scope.x - composerCol.x)).toBeLessThan(3);
    expect(scope.x + scope.width).toBeLessThanOrEqual(composerCol.x + composerCol.width + 1);
    expect(Math.abs(contentCol.x - composerCol.x)).toBeLessThan(3);
    expect(Math.abs(contentCol.x + contentCol.width - (composerCol.x + composerCol.width))).toBeLessThan(3);
  }
}

async function assertComposerCenteredInMain(page: Page) {
  const main = await mainAreaBox(page);
  const shell = await page.getByTestId("chat-composer-shell").boundingBox();
  expect(main).not.toBeNull();
  expect(shell).not.toBeNull();
  if (main && shell) {
    const mainCenter = main.x + main.width / 2;
    const composerCenter = shell.x + shell.width / 2;
    expect(Math.abs(mainCenter - composerCenter)).toBeLessThan(4);
    expect(shell.width).toBeLessThanOrEqual(768 + 2);
  }
}

const SEED_CONV_ID = "e2e-composer-layout-conv";

async function openSeededConversation(page: Page, theme: "dark" | "light", sidebarCollapsed: boolean) {
  await page.addInitScript(
    ({ themeKey, themeValue, sidebarKey, collapsed, convId, storageKey }) => {
      localStorage.setItem(themeKey, themeValue);
      localStorage.setItem(sidebarKey, collapsed ? "1" : "0");
      const now = new Date().toISOString();
      const conv = {
        id: convId,
        title: "Summarize a policy",
        projectId: null,
        createdAt: now,
        updatedAt: now,
        messages: [
          {
            id: "e2e-user-1",
            role: "user",
            content: "Summarize a policy",
            createdAt: now,
          },
          {
            id: "e2e-asst-1",
            role: "assistant",
            content: "Select a project to search your documents.",
            createdAt: now,
            meta: { conversational: true },
          },
        ],
      };
      localStorage.setItem(storageKey, JSON.stringify([conv]));
    },
    {
      themeKey: "aqrem_theme",
      themeValue: theme,
      sidebarKey: "aqrem_sidebar_collapsed",
      collapsed: sidebarCollapsed,
      convId: SEED_CONV_ID,
      storageKey: "aqrem_chat_conversations_v1",
    },
  );
  await page.goto(`/c/${SEED_CONV_ID}`);
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("chat-messages-column")).toBeVisible();
}

for (const viewport of VIEWPORTS) {
  for (const theme of ["dark", "light"] as const) {
    for (const collapsed of [false, true] as const) {
      test.describe(`composer ${viewport.width}x${viewport.height} ${theme} ${collapsed ? "collapsed" : "expanded"}`, () => {
        test.use({
          storageState: authFile,
          viewport,
          colorScheme: theme,
        });

        test("layout metrics and alignment", async ({ page }) => {
          test.setTimeout(90_000);
          await openChat(page, theme, collapsed);
          await assertColumnAlignment(page);

          const shellEmpty = await page.getByTestId("chat-composer-shell").boundingBox();
          expect(shellEmpty).not.toBeNull();
          if (shellEmpty) {
            expect(shellEmpty.height).toBeGreaterThanOrEqual(54);
            expect(shellEmpty.height).toBeLessThanOrEqual(64);
          }

          await assertComposerCenteredInMain(page);
          await assertComposerInViewport(page);
          await assertNoHorizontalPageScroll(page);

          const resize = await page.getByTestId("chat-composer-input").evaluate((el) => getComputedStyle(el).resize);
          expect(resize).toBe("none");

          await expect(page.getByTestId("chat-composer-send")).toBeDisabled();
          await page.getByTestId("chat-composer-input").fill("Hello");
          await expect(page.getByTestId("chat-composer-send")).toBeEnabled();
          await expect(page.getByTestId("chat-composer-send")).toHaveClass(/chat-composer-send-ready/);

          await openSeededConversation(page, theme, collapsed);
          await assertColumnAlignment(page);
          await assertComposerCenteredInMain(page);

          await page.getByTestId("chat-composer-input").fill("Line one\nLine two\nLine three");
          await page.keyboard.press("Shift+Enter");
          await page.getByTestId("chat-composer-input").type("Line four");
          const value = await page.getByTestId("chat-composer-input").inputValue();
          expect(value.split("\n").length).toBeGreaterThanOrEqual(4);

          const longText = Array.from({ length: 12 }, (_, i) => `Line ${i + 1}`).join("\n");
          await page.getByTestId("chat-composer-input").fill(longText);
          const inputBox = await page.getByTestId("chat-composer-input").boundingBox();
          expect(inputBox).not.toBeNull();
          if (inputBox) {
            expect(inputBox.height).toBeLessThanOrEqual(204);
          }

          mkdirSync(SHOT_DIR, { recursive: true });
          await page.screenshot({
            path: join(
              SHOT_DIR,
              `after-${viewport.width}x${viewport.height}-${theme}-${collapsed ? "collapsed" : "expanded"}.png`,
            ),
            fullPage: false,
          });
        });
      });
    }
  }
}

test.describe("composer keyboard and attachments", () => {
  test.use({ storageState: authFile, viewport: { width: 1440, height: 900 } });

  test("Enter sends and keeps focus; attachment chip inside shell", async ({ page }) => {
    await openSeededConversation(page, "dark", false);
    const composer = page.getByTestId("chat-composer-input");
    await composer.fill("Another question");
    await composer.press("Enter");
    await expect(page.locator(".ref-user-bubble").filter({ hasText: "Another question" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(composer).toBeFocused({ timeout: 10_000 });

    await page.setInputFiles('input[type="file"]', {
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("sample attachment"),
    });
    await expect(page.locator(".chat-composer-attachment-chip")).toBeVisible();
    const chip = await page.locator(".chat-composer-attachment-chip").boundingBox();
    const shell = await page.getByTestId("chat-composer-shell").boundingBox();
    expect(chip).not.toBeNull();
    expect(shell).not.toBeNull();
    if (chip && shell) {
      expect(chip.y).toBeGreaterThanOrEqual(shell.y);
      expect(chip.y + chip.height).toBeLessThanOrEqual(shell.y + shell.height + 1);
    }
  });
});
