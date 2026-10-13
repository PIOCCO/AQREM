import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";

const authFile = join(import.meta.dirname, ".auth/employee.json");

async function openChat(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 20_000 });
}

async function sidebarWidth(page: Page) {
  return page.getByTestId("chat-sidebar").evaluate((el) => el.getBoundingClientRect().width);
}

async function mainLeft(page: Page) {
  return page.locator(".app-main").evaluate((el) => el.getBoundingClientRect().left);
}

async function topBarHeight(page: Page) {
  return page.locator(".ref-chat-header").evaluate((el) => el.getBoundingClientRect().height);
}

async function assertNoPageScroll(page: Page) {
  const overflow = await page.evaluate(() => ({
    doc: document.documentElement.scrollHeight <= document.documentElement.clientHeight + 1,
    body: document.body.scrollHeight <= document.body.clientHeight + 1,
  }));
  expect(overflow.doc).toBe(true);
  expect(overflow.body).toBe(true);
}

async function assertComposerVisible(page: Page) {
  const composer = page.getByRole("textbox", { name: "Message" });
  await expect(composer).toBeVisible();
  const disclaimer = page.getByText(/AQREM can make mistakes/);
  await expect(disclaimer).toBeVisible();
  const box = await disclaimer.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  if (box && viewport) {
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 1);
  }
}

async function assertContentColumnAligned(page: Page) {
  const header = await page.locator(".ref-chat-header-inner").boundingBox();
  const composerColumn = await page.locator(".ref-composer-dock .ref-content-column").boundingBox();
  expect(header).not.toBeNull();
  expect(composerColumn).not.toBeNull();
  if (header && composerColumn) {
    expect(Math.abs(header.x - composerColumn.x)).toBeLessThan(3);
    expect(Math.abs(header.x + header.width - (composerColumn.x + composerColumn.width))).toBeLessThan(3);
  }
}

test.describe("sidebar layout", () => {
  test.use({ storageState: authFile, viewport: { width: 1440, height: 900 } });

  test("expanded desktop metrics @1440", async ({ page }) => {
    await openChat(page);
    await page.evaluate(() => localStorage.setItem("aqrem_sidebar_collapsed", "0"));
    await page.reload();
    await openChat(page);

    const w = await sidebarWidth(page);
    expect(w).toBeGreaterThan(268);
    expect(w).toBeLessThan(276);

    const mainX = await mainLeft(page);
    expect(mainX).toBeGreaterThan(268);

    expect(await topBarHeight(page)).toBeGreaterThan(54);
    expect(await topBarHeight(page)).toBeLessThan(58);

    await expect(page.getByTestId("sidebar-toggle")).toHaveCount(1);
    await assertComposerVisible(page);
    await assertContentColumnAligned(page);
    await assertNoPageScroll(page);
  });

  test("collapsed desktop metrics @1440", async ({ page }) => {
    await openChat(page);
    await page.getByTestId("sidebar-toggle").click();
    await page.waitForTimeout(250);

    const w = await sidebarWidth(page);
    expect(w).toBeGreaterThan(60);
    expect(w).toBeLessThan(68);

    const mainXCollapsed = await mainLeft(page);
    expect(mainXCollapsed).toBeLessThan(80);

    expect(await topBarHeight(page)).toBeGreaterThan(54);
    expect(await topBarHeight(page)).toBeLessThan(58);

    await expect(page.getByTestId("sidebar-toggle")).toHaveCount(1);
    await assertComposerVisible(page);
    await assertNoPageScroll(page);

    const railIcons = page.locator(".sidebar-rail-nav .sidebar-rail-btn, .sidebar-rail-nav a.sidebar-rail-btn");
    expect(await railIcons.count()).toBeGreaterThanOrEqual(10);
  });

  test("Ctrl+B toggles and persists", async ({ page }) => {
    await openChat(page);
    await page.keyboard.press(process.platform === "darwin" ? "Meta+b" : "Control+b");
    await page.waitForTimeout(250);
    let w = await sidebarWidth(page);
    expect(w).toBeLessThan(68);

    await page.reload();
    await openChat(page);
    w = await sidebarWidth(page);
    expect(w).toBeLessThan(68);
  });
});

test.describe("sidebar layout 1280x720", () => {
  test.use({ storageState: authFile, viewport: { width: 1280, height: 720 } });

  test("composer visible expanded and collapsed", async ({ page }) => {
    await openChat(page);
    await page.evaluate(() => localStorage.setItem("aqrem_sidebar_collapsed", "0"));
    await page.reload();
    await openChat(page);
    await assertComposerVisible(page);

    await page.getByTestId("sidebar-toggle").click();
    await page.waitForTimeout(250);
    await assertComposerVisible(page);
    await assertNoPageScroll(page);
  });
});

test.describe("mobile drawer", () => {
  test.use({ storageState: authFile, viewport: { width: 390, height: 844 } });

  test("drawer opens from header and closes with Escape", async ({ page }) => {
    await openChat(page);
    await page.getByRole("button", { name: "Open sidebar" }).click();
    await expect(page.getByTestId("chat-sidebar")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("chat-sidebar")).not.toHaveClass(/chat-sidebar-mobile-open/);
  });
});
