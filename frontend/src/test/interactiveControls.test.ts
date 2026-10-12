import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name === "test") continue;
      walk(p, out);
    } else if (/\.(tsx|jsx)$/.test(name)) {
      out.push(p);
    }
  }
  return out;
}

/** Rough static check: native buttons must have onClick, type=submit, or be disabled. */
function findSuspiciousButtons(source: string, file: string): string[] {
  const issues: string[] = [];
  const buttonRe = /<button\b[^>]*>/g;
  let m: RegExpExecArray | null;
  while ((m = buttonRe.exec(source))) {
    const tag = m[0];
    const line = source.slice(0, m.index).split("\n").length;
    if (/type=["']submit["']/.test(tag)) continue;
    if (/\bdisabled\b/.test(tag)) continue;
    if (/\bonClick=/.test(tag)) continue;
    if (/\bform=/.test(tag)) continue;
    issues.push(`${file}:${line} button missing onClick/disabled/submit: ${tag.slice(0, 80)}…`);
  }
  return issues;
}

function findLinksWithoutHref(source: string, file: string): string[] {
  const issues: string[] = [];
  const linkRe = /<Link\b[^>]*>/g;
  let m: RegExpExecArray | null;
  while ((m = linkRe.exec(source))) {
    const tag = m[0];
    const line = source.slice(0, m.index).split("\n").length;
    if (/\bto=/.test(tag)) continue;
    issues.push(`${file}:${line} Link missing to=`);
  }
  return issues;
}

function findButtonsWithoutAccessibleName(source: string, file: string): string[] {
  const issues: string[] = [];
  const buttonRe = /<button\b[\s\S]*?<\/button>/g;
  let m: RegExpExecArray | null;
  while ((m = buttonRe.exec(source))) {
    const block = m[0];
    const open = block.slice(0, block.indexOf(">") + 1);
    const line = source.slice(0, m.index).split("\n").length;
    if (/aria-label=/.test(open)) continue;
    if (/aria-labelledby=/.test(open)) continue;
    const inner = block.replace(/<[^>]+>/g, "").trim();
    if (inner.length > 0) continue;
    if (/<svg\b/.test(block) && /aria-hidden/.test(block)) {
      issues.push(`${file}:${line} icon-only button missing aria-label`);
    }
  }
  return issues;
}

describe("interactive controls (static)", () => {
  it("buttons have handlers or are intentionally disabled", () => {
    const files = walk(SRC);
    const all: string[] = [];
    for (const file of files) {
      const src = readFileSync(file, "utf8");
      all.push(...findSuspiciousButtons(src, file.replace(SRC + "/", "")));
    }
    expect(all).toEqual([]);
  });

  it("react-router Link components have to=", () => {
    const files = walk(SRC);
    const all: string[] = [];
    for (const file of files) {
      const src = readFileSync(file, "utf8");
      all.push(...findLinksWithoutHref(src, file.replace(SRC + "/", "")));
    }
    expect(all).toEqual([]);
  });

  it("icon-only buttons declare aria-label", () => {
    const files = walk(SRC);
    const all: string[] = [];
    for (const file of files) {
      const src = readFileSync(file, "utf8");
      all.push(...findButtonsWithoutAccessibleName(src, file.replace(SRC + "/", "")));
    }
    expect(all).toEqual([]);
  });
});
