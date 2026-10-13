import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { mkdirSync } from "node:fs";

const authFile = join(import.meta.dirname, ".auth/employee.json");
const SHOT_DIR = join(import.meta.dirname, "../../artifacts/composer-autogrow");

const VIEWPORTS = [
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
] as const;

const SEED_CONV_ID = "e2e-autogrow-conv";

async function openSeeded(page: Page, theme: "dark" | "light", collapsed: boolean) {
  await page.addInitScript(
    ({ themeKey, themeValue, sidebarKey, collapsed: c, convId, storageKey }) => {
      localStorage.setItem(themeKey, themeValue);
      localStorage.setItem(sidebarKey, c ? "1" : "0");
      const now = new Date().toISOString();
      const conv = {
        id: convId,
        title: "Auto-grow",
        projectId: null,
        createdAt: now,
        updatedAt: now,
        messages: Array.from({ length: 24 }, (_, i) => ({
          id: `m-${i}`,
          role: i % 2 === 0 ? "user" : "assistant",
          content: `Message ${i + 1} with enough text to scroll the thread on tall viewports and keep history visible.`,
          createdAt: now,
          ...(i % 2 === 1 ? { meta: { conversational: true } } : {}),
        })),
      };
      localStorage.setItem(storageKey, JSON.stringify([conv]));
    },
    {
      themeKey: "aqrem_theme",
      themeValue: theme,
      sidebarKey: "aqrem_sidebar_collapsed",
      collapsed,
      convId: SEED_CONV_ID,
      storageKey: "aqrem_chat_conversations_v1",
    },
  );
  await page.goto(`/c/${SEED_CONV_ID}`);
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 20_000 });
}

function lines(n: number) {
  return Array.from({ length: n }, (_, i) => `Line ${i + 1}`).join("\n");
}

async function shellMetrics(page: Page) {
  return page.getByTestId("chat-composer-shell").evaluate((el) => {
    const box = el.getBoundingClientRect();
    return { height: box.height, bottom: box.bottom, width: box.width };
  });
}

async function inputMetrics(page: Page) {
  return page.getByTestId("chat-composer-input").evaluate((el) => {
    const box = el.getBoundingClientRect();
    const cap = Number.parseFloat(getComputedStyle(el).maxHeight);
    return {
      height: box.height,
      scrollTop: el.scrollTop,
      cap: Number.isFinite(cap) ? cap : 150,
      resize: getComputedStyle(el).resize,
    };
  });
}

for (const viewport of VIEWPORTS) {
  for (const theme of ["dark", "light"] as const) {
    for (const collapsed of [false, true] as const) {
      test.describe(`autogrow ${viewport.width}x${viewport.height} ${theme} ${collapsed ? "collapsed" : "expanded"}`, () => {
        test.use({ storageState: authFile, viewport, colorScheme: theme });

        test("height growth, cap, width, bottom anchor, send reset", async ({ page }) => {
          test.setTimeout(120_000);
          await openSeeded(page, theme, collapsed);
          const composer = page.getByTestId("chat-composer-input");

          const empty = await shellMetrics(page);
          expect(empty.height).toBeGreaterThanOrEqual(54);
          expect(empty.height).toBeLessThanOrEqual(60);
          const width0 = empty.width;

          const h2 = await (async () => {
            await composer.fill(lines(2));
            await page.waitForTimeout(80);
            return shellMetrics(page);
          })();
          const h3 = await (async () => {
            await composer.fill(lines(3));
            await page.waitForTimeout(80);
            return shellMetrics(page);
          })();
          const h4 = await (async () => {
            await composer.fill(lines(4));
            await page.waitForTimeout(80);
            return shellMetrics(page);
          })();

          expect(h3.height - h2.height).toBeGreaterThan(18);
          expect(h3.height - h2.height).toBeLessThan(32);
          expect(h4.height - h3.height).toBeGreaterThan(18);
          expect(h4.height - h3.height).toBeLessThan(32);
          expect(Math.abs(h4.bottom - empty.bottom)).toBeLessThan(2);

          const capped = await (async () => {
            await composer.fill(lines(10));
            await page.waitForTimeout(100);
            return { shell: await shellMetrics(page), input: await inputMetrics(page) };
          })();

          const capPx = await page.evaluate(() => Math.min(150, window.innerHeight * 0.3));
          expect(capped.shell.height).toBeLessThanOrEqual(capPx + 28);
          expect(capped.input.height).toBeLessThanOrEqual(capPx + 2);
          expect(capped.input.scrollTop).toBeGreaterThanOrEqual(0);
          expect(capped.input.resize).toBe("none");
          expect(capped.shell.width).toBeCloseTo(width0, 0);

          await composer.fill("");
          await page.waitForTimeout(80);
          const cleared = await shellMetrics(page);
          expect(cleared.height).toBeGreaterThanOrEqual(54);
          expect(cleared.height).toBeLessThanOrEqual(60);

          await composer.fill("Send reset check");
          await composer.press("Enter");
          await expect(page.locator(".ref-user-bubble").filter({ hasText: "Send reset check" })).toBeVisible({
            timeout: 30_000,
          });
          await page.waitForTimeout(100);
          const afterSend = await shellMetrics(page);
          expect(afterSend.height).toBeGreaterThanOrEqual(54);
          expect(afterSend.height).toBeLessThanOrEqual(60);
        });

        test("message list anchor at bottom and while scrolled up", async ({ page }) => {
          await openSeeded(page, theme, collapsed);
          const scroll = page.locator(".ref-conversation-scroll");
          await scroll.evaluate((el) => {
            el.scrollTop = el.scrollHeight;
          });
          const composer = page.getByTestId("chat-composer-input");
          await composer.fill(lines(5));
          await page.waitForTimeout(150);
          const distBottom = await scroll.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight);
          expect(distBottom).toBeLessThan(120);

          await scroll.evaluate((el) => {
            el.scrollTop = 0;
          });
          const scrollTopBefore = await scroll.evaluate((el) => el.scrollTop);
          await composer.fill(lines(6));
          await page.waitForTimeout(150);
          const scrollTopAfter = await scroll.evaluate((el) => el.scrollTop);
          expect(scrollTopAfter).toBe(scrollTopBefore);
        });

        test("paste cap and attachment shell limit", async ({ page }) => {
          await openSeeded(page, theme, collapsed);
          const composer = page.getByTestId("chat-composer-input");
          const pasted = lines(50);
          await composer.fill(pasted);
          await page.waitForTimeout(120);
          const input = await inputMetrics(page);
          const capPx = await page.evaluate(() => Math.min(150, window.innerHeight * 0.3));
          expect(input.height).toBeLessThanOrEqual(capPx + 2);
          expect(input.scrollTop + input.height).toBeGreaterThan(capPx - 4);

          await page.setInputFiles('input[type="file"]', [
            { name: "a.txt", mimeType: "text/plain", buffer: Buffer.from("a") },
            { name: "b.txt", mimeType: "text/plain", buffer: Buffer.from("b") },
          ]);
          await composer.fill(lines(4));
          await page.waitForTimeout(100);
          const shellMax = await page.evaluate(() => window.innerHeight * 0.4);
          const shellH = (await shellMetrics(page)).height;
          expect(shellH).toBeLessThanOrEqual(shellMax + 4);
        });
      });
    }
  }
}

test.describe("autogrow screenshots", () => {
  test.use({ storageState: authFile, viewport: { width: 1440, height: 900 }, colorScheme: "dark" });

  test("1, 3 and 8 lines", async ({ page }) => {
    await openSeeded(page, "dark", false);
    mkdirSync(SHOT_DIR, { recursive: true });
    const composer = page.getByTestId("chat-composer-input");
    for (const n of [1, 3, 8] as const) {
      await composer.fill(lines(n));
      await page.waitForTimeout(120);
      await page.screenshot({ path: join(SHOT_DIR, `after-${n}-lines-1440-dark.png`) });
    }
  });
});
