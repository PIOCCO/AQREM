import { describe, expect, it } from "vitest";
import { licenseBannerFor } from "./licenseStatus";

describe("licenseBannerFor", () => {
  it("shows nothing in shared mode or when licensed", () => {
    expect(licenseBannerFor(null)).toBeNull();
    expect(licenseBannerFor({ mode: "shared", level: "ok", read_only: false })).toBeNull();
    expect(licenseBannerFor({ mode: "dedicated", level: "ok", read_only: false, message: "Licensed" })).toBeNull();
  });

  it("warns admins during warning and grace", () => {
    const w = licenseBannerFor({ mode: "dedicated", level: "warning", read_only: false, message: "expires soon" });
    expect(w?.tone).toBe("warning");
    const g = licenseBannerFor({ mode: "dedicated", level: "grace", read_only: false, message: "expired" });
    expect(g?.title).toBe("License grace period");
  });

  it("hides warning for non-admins (empty message) but always shows read-only", () => {
    expect(licenseBannerFor({ mode: "dedicated", level: "grace", read_only: false, message: "" })).toBeNull();
    const r = licenseBannerFor({ mode: "dedicated", level: "read_only", read_only: true, message: "" });
    expect(r?.tone).toBe("danger");
    expect(r?.text).toContain("read-only");
  });
});
