import { describe, expect, it } from "vitest";
import { activityDayLabel, formatActivityTime, initialsFromName } from "./activityFormat";

describe("activityFormat", () => {
  it("formats relative time under 7 days", () => {
    const now = new Date("2026-01-10T12:00:00Z");
    const r = formatActivityTime("2026-01-10T11:30:00Z", now);
    expect(r.relative).toMatch(/min ago/);
  });

  it("formats absolute date beyond 7 days", () => {
    const now = new Date("2026-01-10T12:00:00Z");
    const r = formatActivityTime("2025-12-01T10:00:00Z", now);
    expect(r.relative).not.toMatch(/ago/);
  });

  it("labels today and yesterday", () => {
    const now = new Date("2026-03-15T12:00:00Z");
    expect(activityDayLabel("2026-03-15T08:00:00Z", now)).toBe("Today");
    expect(activityDayLabel("2026-03-14T08:00:00Z", now)).toBe("Yesterday");
  });

  it("initials from name", () => {
    expect(initialsFromName("Ada Lovelace")).toBe("AL");
  });
});
