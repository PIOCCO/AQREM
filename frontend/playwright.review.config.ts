import { defineConfig, devices } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  use: {
    ...base.use,
    baseURL: process.env.QA_BASE_URL ?? "http://127.0.0.1:4173",
  },
  webServer: process.env.QA_BASE_URL
    ? undefined
    : {
        command: "VITE_PREVIEW_PORT=4173 npm run preview",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: true,
        timeout: 120_000,
      },
  projects: [
    {
      name: "review",
      testMatch: /product-review-walkthrough|platform-admin-privacy\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], colorScheme: "dark" },
    },
  ],
});
