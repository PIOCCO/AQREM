import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const FORBIDDEN = [
  "PLATFORM_ADMIN_EMAIL",
  "backend/.env",
  "Platform operators:",
  "Create account",
  "registerUser",
];

describe("public surface leaks", () => {
  it("login page source contains no operator hints", () => {
    const src = readFileSync(join(import.meta.dirname, "../pages/LoginPage.tsx"), "utf8");
    for (const needle of FORBIDDEN) {
      expect(src).not.toContain(needle);
    }
  });

  it("production bundle has no operator hints when dist exists", () => {
    const distAssets = join(import.meta.dirname, "../../dist/assets");
    let files: string[] = [];
    try {
      files = readdirSync(distAssets).filter((f) => f.endsWith(".js"));
    } catch {
      return;
    }
    expect(files.length).toBeGreaterThan(0);
    const combined = files.map((f) => readFileSync(join(distAssets, f), "utf8")).join("\n");
    for (const needle of FORBIDDEN) {
      expect(combined).not.toContain(needle);
    }
  });
});
