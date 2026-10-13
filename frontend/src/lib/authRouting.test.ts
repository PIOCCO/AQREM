import { describe, expect, it } from "vitest";
import { isPlatformSessionToken, resolvePostAuthPath } from "./authRouting";

function fakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none" }));
  const body = btoa(JSON.stringify(payload)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${header}.${body}.sig`;
}

describe("resolvePostAuthPath", () => {
  it("sends org admin invite accept to company admin console", () => {
    const token = fakeJwt({ aud: "aqrem-org-admin", organization_id: "11111111-1111-4111-8111-111111111111" });
    expect(
      resolvePostAuthPath({
        access_token: token,
        organization_id: "11111111-1111-4111-8111-111111111111",
        role: "ORG_ADMIN",
      }),
    ).toBe("/admin");
  });

  it("sends platform token without org to master admin", () => {
    const token = fakeJwt({ aud: "aqrem-master" });
    expect(isPlatformSessionToken(token)).toBe(true);
    expect(resolvePostAuthPath({ access_token: token, role: null })).toBe("/master-admin");
  });
});
