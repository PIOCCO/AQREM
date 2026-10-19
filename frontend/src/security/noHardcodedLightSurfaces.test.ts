import { readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join, sep } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const ALLOW_FILES = new Set(["index.css", "themeContrast.test.ts"]);
const FORBIDDEN = [
  /\bbg-white\b/,
  /\bbg-slate-\d+/,
  /\bbg-gray-\d+/,
  /\bbg-neutral-\d+/,
  /#fff(?:fff)?\b/i,
  /#f5f5f3/i,
];

function walk(dir: string, out: string[] = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (name === "node_modules" || name === "dist") continue;
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (/\.(tsx|ts|css)$/.test(name)) out.push(p);
  }
  return out;
}

describe("no hard-coded light surfaces in components", () => {
  it("flags bg-white/slate/gray and common light hex in TS/TSX", () => {
    const violations: string[] = [];
    for (const file of walk(SRC)) {
      const base = basename(file);
      if (ALLOW_FILES.has(base) || file.includes(`${sep}security${sep}`)) continue;
      if (base.endsWith(".css")) continue;
      const text = readFileSync(file, "utf8");
      for (const re of FORBIDDEN) {
        if (re.test(text)) {
          violations.push(`${file}: ${re.source}`);
        }
      }
    }
    expect(violations, violations.join("\n")).toEqual([]);
  });
});
