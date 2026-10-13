import { describe, expect, it } from "vitest";
import { isUuid, normalizeOrganizationId } from "./uuid";

describe("isUuid", () => {
  it("accepts valid v4 ids", () => {
    expect(isUuid("550e8400-e29b-41d4-a716-446655440000")).toBe(true);
  });

  it("rejects garbage", () => {
    expect(isUuid("not-a-uuid")).toBe(false);
    expect(isUuid("")).toBe(false);
  });
});

describe("normalizeOrganizationId", () => {
  it("drops literal null and invalid values", () => {
    expect(normalizeOrganizationId("null")).toBeNull();
    expect(normalizeOrganizationId("undefined")).toBeNull();
    expect(normalizeOrganizationId("not-a-uuid")).toBeNull();
  });

  it("keeps valid UUIDs", () => {
    expect(normalizeOrganizationId("550e8400-e29b-41d4-a716-446655440000")).toBe(
      "550e8400-e29b-41d4-a716-446655440000",
    );
  });
});
