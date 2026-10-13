import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const loginSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "LoginPage.tsx"),
  "utf8",
);

describe("LoginPage", () => {
  it("shows sign in only without public registration UI", () => {
    expect(loginSource).toMatch(/Sign in to AQREM/);
    expect(loginSource).toMatch(/Need access\? Ask your organization admin/);
    expect(loginSource).toMatch(/role="alert"/);
    expect(loginSource).not.toMatch(/>\s*Register\s*</);
    expect(loginSource).not.toMatch(/registerUser/);
    expect(loginSource).not.toMatch(/Create account/);
  });
});
