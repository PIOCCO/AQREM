import { describe, expect, it } from "vitest";
import { resolveThemeFromStorage } from "./themeInit";

describe("resolveThemeFromStorage", () => {
  it("defaults new users to dark", () => {
    expect(resolveThemeFromStorage(null)).toBe("dark");
  });

  it("respects explicit light and dark", () => {
    expect(resolveThemeFromStorage("light")).toBe("light");
    expect(resolveThemeFromStorage("dark")).toBe("dark");
  });
});
