import { describe, expect, it } from "vitest";
import { ADMIN_CONSOLE_ACCESS, hasAdminConsoleAccess } from "./permissions";

describe("hasAdminConsoleAccess", () => {
  it("returns true only when permission is present", () => {
    expect(hasAdminConsoleAccess([ADMIN_CONSOLE_ACCESS])).toBe(true);
    expect(hasAdminConsoleAccess([])).toBe(false);
    expect(hasAdminConsoleAccess(undefined)).toBe(false);
  });
});
