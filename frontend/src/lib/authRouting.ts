import { normalizeOrganizationId } from "./uuid";

export function parseJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function tokenAudience(token: string): string | null {
  const aud = parseJwtPayload(token)?.aud;
  return typeof aud === "string" ? aud : null;
}

export function isPlatformSessionToken(token: string): boolean {
  return tokenAudience(token) === "aqrem-master";
}

export function organizationIdFromToken(token: string): string | null {
  const raw = parseJwtPayload(token)?.organization_id;
  return normalizeOrganizationId(typeof raw === "string" ? raw : null);
}

export function resolveOrganizationIdForSession(
  token: string,
  organizationId: string | null | undefined,
): string | null {
  return normalizeOrganizationId(organizationId ?? null) ?? organizationIdFromToken(token);
}

type PostAuthPayload = {
  access_token: string;
  organization_id?: string | null;
  role?: string | null;
  is_platform_admin?: boolean;
  must_change_password?: boolean;
};

/** Where to send the user immediately after login or accepting an invitation. */
export function resolvePostAuthPath(payload: PostAuthPayload, nextPath = "/"): string {
  if (payload.must_change_password) return "/change-password";

  const orgId = resolveOrganizationIdForSession(payload.access_token, payload.organization_id ?? null);
  const platformToken = isPlatformSessionToken(payload.access_token);

  if (platformToken && !orgId) return "/master-admin";
  if (payload.role === "ORG_ADMIN") return "/admin";
  if (platformToken && nextPath.includes("master-admin")) return "/master-admin";
  return nextPath.startsWith("/") ? nextPath : "/";
}
