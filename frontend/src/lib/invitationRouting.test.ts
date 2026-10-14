import { describe, expect, it } from "vitest";
import { acceptInviteUrlForToken, extractRootPastedToken } from "./invitationRouting";

describe("extractRootPastedToken", () => {
  it("detects pasted opaque token paths", () => {
    const token = "DWIJ78687dewadawd@@qqjyggjqqqbhj667qqeada";
    expect(extractRootPastedToken(`/${token}`)).toBe(token);
    expect(acceptInviteUrlForToken(token)).toContain(encodeURIComponent("@@"));
  });

  it("ignores known app routes", () => {
    expect(extractRootPastedToken("/super-admin/organizations")).toBeNull();
    expect(extractRootPastedToken("/login")).toBeNull();
    expect(extractRootPastedToken("/chat")).toBeNull();
  });
});
