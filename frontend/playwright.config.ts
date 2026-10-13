import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  webServer: {
    command: "VITE_PREVIEW_PORT=5173 npm run preview",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    {
      name: "audit",
      testMatch: /authenticated-audit\.spec\.ts|contrast-regression\.spec\.ts|chat-sidebar\.spec\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 720 } },
    },
    {
      name: "sidebar-layout",
      testMatch:
        /sidebar-layout\.spec\.ts|chat-share\.spec\.ts|activity-page\.spec\.ts|chat-composer-layout\.spec\.ts|chat-composer-autogrow\.spec\.ts|new-questionnaire-dialog\.spec\.ts|logo-home\.spec\.ts|admin-console-nav\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth/employee.json",
        viewport: { width: 1440, height: 900 },
      },
    },
    { name: "public-dark", testMatch: /public-a11y|dead-controls/, use: { ...devices["Desktop Chrome"], colorScheme: "dark" } },
    { name: "public-light", testMatch: /public-a11y|dead-controls/, use: { ...devices["Desktop Chrome"], colorScheme: "light" } },
  ],
});
