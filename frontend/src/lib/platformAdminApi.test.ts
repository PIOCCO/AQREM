import { describe, expect, it } from "vitest";
import { normalizeOrganization } from "./platformAdminApi";

describe("normalizeOrganization", () => {
  it("maps legacy array item with active_seats", () => {
    const org = normalizeOrganization({
      id: "abc",
      name: "Legacy Co",
      slug: "legacy",
      license_limit: 10,
      license_status: "active",
      is_active: true,
      active_seats: 3,
    });
    expect(org.seats.seats_used).toBe(3);
    expect(org.seats.seats_limit).toBe(10);
    expect(org.environment).toBe("production");
  });
});
