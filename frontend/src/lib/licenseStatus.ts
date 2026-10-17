import { resolveApiBase } from "./apiBase";
import { normalizeOrganizationId } from "./uuid";
import type { AuthSession } from "./api";

/** Dedicated-tier license state as returned by GET /api/v1/license/status. */
export type LicenseStatus = {
  mode: "shared" | "dedicated";
  level: "ok" | "warning" | "grace" | "read_only";
  read_only: boolean;
  message?: string;
  code?: string;
  grace_until?: string | null;
  expires_at?: string | null;
};

export type LicenseBanner = { tone: "warning" | "danger"; text: string; title: string };

/** Pure mapping used by the banner (shown only in dedicated mode, never when everything is fine). */
export function licenseBannerFor(status: LicenseStatus | null | undefined): LicenseBanner | null {
  if (!status || status.mode !== "dedicated" || status.level === "ok") return null;
  const text = (status.message || "").trim();
  if (status.level === "read_only") {
    return {
      tone: "danger",
      title: "Read-only mode",
      text: text || "AQREM is currently in read-only mode. Existing content remains available.",
    };
  }
  if (!text) return null; // non-admins only see the read-only notice
  return { tone: "warning", title: status.level === "grace" ? "License grace period" : "License notice", text };
}

export async function fetchLicenseStatus(session: AuthSession): Promise<LicenseStatus | null> {
  const headers: Record<string, string> = { Authorization: `Bearer ${session.token}` };
  const orgId = normalizeOrganizationId(session.organizationId);
  if (orgId) headers["X-Organization-Id"] = orgId;
  try {
    const res = await fetch(`${resolveApiBase()}/api/v1/license/status`, { headers });
    if (!res.ok) return null;
    return (await res.json()) as LicenseStatus;
  } catch {
    return null;
  }
}
