import { readApiError } from "./errors";
import type { AuthSession } from "./api";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type AdminApiError = { code: string; message: string; field?: string };

export type SeatUsage = {
  active_members: number;
  pending_invitations: number;
  seats_used: number;
  seats_limit: number;
  seats_available: number;
  is_full: boolean;
};

export type AdminOrganization = {
  id: string;
  name: string;
  slug: string;
  license_limit: number;
  license_status: string;
  environment: string;
  is_active: boolean;
  owner_display_name: string | null;
  created_at: string;
  license_renews_at: string | null;
  seats: SeatUsage;
};

export type AdminOrgList = {
  items: AdminOrganization[];
  counts: Record<string, number>;
};

export type DirectoryRow = {
  row_id: string;
  kind: "member" | "invitation";
  membership_id?: string;
  invitation_id?: string;
  user_id?: string;
  full_name: string;
  email: string;
  role: string;
  status: string;
};

export type AdminContext = {
  licensing_test_mode: boolean;
  test_mode_effective: boolean;
};

function adminHeaders(session: AuthSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.token}`,
    "Content-Type": "application/json",
  };
}

async function parseError(res: Response, fallback: string): Promise<never> {
  try {
    const body = await res.json();
    if (body?.detail?.code) {
      const err: AdminApiError = body.detail;
      throw Object.assign(new Error(err.message), { admin: err });
    }
  } catch (e) {
    if (e instanceof Error && "admin" in e) throw e;
  }
  throw new Error(await readApiError(res, fallback));
}

export async function fetchAdminContext(session: AuthSession): Promise<AdminContext> {
  const res = await fetch(`${API_BASE}/api/v1/admin/context`, { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load admin context"));
  return res.json();
}

export async function fetchAdminOrganizations(
  session: AuthSession,
  params?: { q?: string; status?: string },
): Promise<AdminOrgList> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.status && params.status !== "all") qs.set("status", params.status);
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations?${qs}`, { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load organizations"));
  return res.json();
}

export async function createAdminOrganization(
  session: AuthSession,
  payload: {
    name: string;
    license_limit: number;
    environment: string;
    owner_display_name?: string;
  },
): Promise<AdminOrganization> {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations`, {
    method: "POST",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to create organization");
  return res.json();
}

export async function updateAdminOrganization(
  session: AuthSession,
  orgId: string,
  payload: { license_limit?: number; license_status?: string; owner_display_name?: string },
): Promise<AdminOrganization> {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}`, {
    method: "PATCH",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to update organization");
  return res.json();
}

export async function fetchOrganizationDirectory(
  session: AuthSession,
  orgId: string,
  page: number,
  pageSize = 5,
) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/directory?page=${page}&page_size=${pageSize}`,
    { headers: adminHeaders(session) },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load members"));
  return res.json() as Promise<{
    seats: SeatUsage;
    license_status: string;
    license_renews_at: string | null;
    rows: DirectoryRow[];
    total: number;
    page: number;
    page_size: number;
  }>;
}

export async function inviteOrganizationUser(
  session: AuthSession,
  orgId: string,
  payload: { email: string; full_name: string; role: string },
) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/users`, {
    method: "POST",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to send invitation");
  return res.json() as Promise<{
    invitation_setup_path: string;
    invitation_expires_at: string;
  }>;
}

export async function resendInvitation(session: AuthSession, orgId: string, invitationId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/invitations/${invitationId}/resend`,
    { method: "POST", headers: adminHeaders(session) },
  );
  if (!res.ok) await parseError(res, "Failed to resend invitation");
  return res.json();
}

export async function revokeInvitation(session: AuthSession, orgId: string, invitationId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/invitations/${invitationId}/revoke`,
    { method: "POST", headers: adminHeaders(session) },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Failed to revoke invitation"));
}

export async function updateMemberRole(
  session: AuthSession,
  orgId: string,
  membershipId: string,
  role: string,
) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/members/${membershipId}`, {
    method: "PATCH",
    headers: adminHeaders(session),
    body: JSON.stringify({ role }),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to update role"));
}

export async function deactivateMember(session: AuthSession, orgId: string, membershipId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/members/${membershipId}/deactivate`,
    { method: "POST", headers: adminHeaders(session) },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Failed to remove member"));
}

export async function fetchOrgInvitations(session: AuthSession, orgId: string) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/invitations`, {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load invitations"));
  return res.json();
}

export async function fetchOrgAudit(session: AuthSession, orgId: string) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/audit`, {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load audit log"));
  return res.json() as Promise<{ items: { id: string; created_at: string; actor_email: string; action: string; target: string }[] }>;
}

export function isAdminApiError(e: unknown): e is Error & { admin: AdminApiError } {
  return e instanceof Error && "admin" in e && typeof (e as { admin?: AdminApiError }).admin?.code === "string";
}
