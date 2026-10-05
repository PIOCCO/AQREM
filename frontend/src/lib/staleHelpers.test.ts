import { describe, expect, it } from "vitest";
import {
  canReviewerRevalidate,
  formatStaleStatus,
  regenerationSourceLabel,
  shouldShowStaleWarning,
} from "./staleHelpers";

describe("stale workflow helpers", () => {
  it("shows stale answers in review queue label", () => {
    expect(formatStaleStatus(true)).toBe("Potentially Stale");
  });

  it("shows current label when not stale", () => {
    expect(formatStaleStatus(false)).toBe("Current");
  });

  it("shows stale warning when potentially stale", () => {
    expect(shouldShowStaleWarning(true, 0)).toBe(true);
  });

  it("shows stale warning when evidence changed count > 0", () => {
    expect(shouldShowStaleWarning(false, 2)).toBe(true);
  });

  it("hides stale warning when current and no changes", () => {
    expect(shouldShowStaleWarning(false, 0)).toBe(false);
  });

  it("blocks viewer revalidate actions", () => {
    expect(canReviewerRevalidate("VIEWER")).toBe(false);
  });

  it("allows reviewer revalidate actions", () => {
    expect(canReviewerRevalidate("REVIEWER")).toBe(true);
  });

  it("labels stale regeneration source", () => {
    expect(regenerationSourceLabel("stale_regeneration")).toContain("Regenerated");
  });
});
