import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const FORBIDDEN_LOGIN_STRINGS = ["Create account", "Sign up", ">Register<", "registerUser("];
const FORBIDDEN_PLACEHOLDER_MARKERS = [
  "rounded-md bg-[var(--chat-brand-mark)] flex items-center justify-center text-white font-bold text-sm",
  ">A</div>",
];

function readDistBundle(): string {
  const distAssets = join(import.meta.dirname, "../../dist/assets");
  const files = readdirSync(distAssets).filter((f) => f.endsWith(".js"));
  expect(files.length).toBeGreaterThan(0);
  return files.map((f) => readFileSync(join(distAssets, f), "utf8")).join("\n");
}

describe("login bundle guards", () => {
  it("production bundle has no registration UI strings", () => {
    const combined = readDistBundle();
    for (const needle of FORBIDDEN_LOGIN_STRINGS) {
      expect(combined).not.toContain(needle);
    }
  });

  it("production bundle has no gradient placeholder logo markup", () => {
    const combined = readDistBundle();
    for (const needle of FORBIDDEN_PLACEHOLDER_MARKERS) {
      expect(combined).not.toContain(needle);
    }
  });

  it("production bundle includes real logo asset references", () => {
    const combined = readDistBundle();
    expect(combined).toMatch(/aqrem-logo-(black|white)/);
  });
});
