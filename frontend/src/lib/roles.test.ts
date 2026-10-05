import { describe, expect, it } from "vitest";
import { canEditContent, canReviewAnswers, roleAtLeast } from "./roles";

describe("roles", () => {
  it("VIEWER cannot edit or review", () => {
    expect(canEditContent("VIEWER")).toBe(false);
    expect(canReviewAnswers("VIEWER")).toBe(false);
  });
  it("REVIEWER can review but not edit", () => {
    expect(canReviewAnswers("REVIEWER")).toBe(true);
    expect(canEditContent("REVIEWER")).toBe(false);
  });
  it("EDITOR can edit and review", () => {
    expect(canEditContent("EDITOR")).toBe(true);
    expect(canReviewAnswers("EDITOR")).toBe(true);
  });
  it("hierarchy", () => {
    expect(roleAtLeast("ORG_ADMIN", "EDITOR")).toBe(true);
    expect(roleAtLeast("VIEWER", "EDITOR")).toBe(false);
  });
});
