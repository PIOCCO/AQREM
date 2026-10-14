import { apiErrorMessage, readApiError, readResponseJson } from "./errors";
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
  license_expires_at: string | null;
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
  active_super_admin_count?: number;
  super_admin_warning?: boolean;
};

export type PlatformStaffMember = {
  id: string;
  email: string;
  full_name: string;
  platform_role: string;
  status: string;
  created_at: string;
};

export type PermissionsMatrix = {
  permissions: string[];
  roles: string[];
  matrix: Record<string, Record<string, boolean>>;
  endpoints: Record<string, string>;
};

const DEFAULT_CONTEXT: AdminContext = {
  licensing_test_mode: false,
  test_mode_effective: false,
};

function adminHeaders(session: AuthSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.token}`,
    "Content-Type": "application/json",
  };
}

async function parseError(res: Response, fallback: string): Promise<never> {
  const body = await readResponseJson(res);
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const structured = detail as Record<string, unknown>;
      if (typeof structured.code === "string" && typeof structured.message === "string") {
        const err: AdminApiError = {
          code: structured.code,
          message: structured.message,
          field: typeof structured.field === "string" ? structured.field : undefined,
        };
        throw Object.assign(new Error(err.message), { admin: err });
      }
    }
  }
  throw new Error(apiErrorMessage(body, fallback, res.status));
}

function statusBucket(status: string): string {
  if (status === "test") return "test";
  if (status === "expired") return "expired";
  if (status === "suspended") return "suspended";
  return "active";
}

function computeCounts(items: AdminOrganization[]): Record<string, number> {
  const counts = { all: items.length, active: 0, suspended: 0, expired: 0, test: 0 };
  for (const o of items) {
    const b = statusBucket(o.license_status);
    if (b in counts) counts[b as keyof typeof counts] += 1;
  }
  return counts;
}

/** Supports legacy API payloads (plain array, active_seats instead of seats). */
export function normalizeOrganization(raw: Record<string, unknown>): AdminOrganization {
  const licenseLimit = Number(raw.license_limit ?? 0);
  const legacyActive = Number(raw.active_seats ?? 0);
  const seatsRaw = raw.seats as Partial<SeatUsage> | undefined;
  const seatsUsed = Number(seatsRaw?.seats_used ?? legacyActive);
  const activeMembers = Number(seatsRaw?.active_members ?? legacyActive);
  const pending = Number(seatsRaw?.pending_invitations ?? 0);
  const seats: SeatUsage = {
    active_members: activeMembers,
    pending_invitations: pending,
    seats_used: seatsUsed,
    seats_limit: Number(seatsRaw?.seats_limit ?? licenseLimit),
    seats_available: Number(
      seatsRaw?.seats_available ?? Math.max(0, licenseLimit - seatsUsed),
    ),
    is_full: Boolean(
      seatsRaw?.is_full ??
        (licenseLimit > 0 && seatsUsed >= licenseLimit),
    ),
  };
  const licenseStatus = String(raw.license_status ?? "active");
  return {
    id: String(raw.id),
    name: String(raw.name ?? ""),
    slug: String(raw.slug ?? ""),
    license_limit: licenseLimit,
    license_status: licenseStatus,
    environment: String(
      raw.environment ?? (licenseStatus === "test" ? "test" : "production"),
    ),
    is_active: raw.is_active !== false,
    owner_display_name: (raw.owner_display_name as string | null) ?? null,
    created_at: String(raw.created_at ?? new Date().toISOString()),
    license_renews_at: (raw.license_renews_at as string | null) ?? null,
    license_expires_at: (raw.license_expires_at as string | null) ?? null,
    seats,
  };
}

export async function deleteAdminOrganization(
  session: AuthSession,
  orgId: string,
  confirmName: string,
): Promise<{ organization_id: string; purge_scheduled_at: string; retention_days: number }> {
  const body = JSON.stringify({ confirmName: confirmName });
  const headers = adminHeaders(session);
  let res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/delete`, {
    method: "POST",
    headers,
    body,
  });
  if (res.status === 404 || res.status === 405) {
    res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}`, {
      method: "DELETE",
      headers,
      body,
    });
  }
  if (!res.ok) await parseError(res, "Failed to delete organization");
  return res.json();
}

export async function fetchPlatformStaff(session: AuthSession): Promise<PlatformStaffMember[]> {
  const res = await fetch(`${API_BASE}/api/v1/admin/platform-staff`, { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load platform team"));
  return res.json();
}

export async function fetchPermissionsMatrix(session: AuthSession): Promise<PermissionsMatrix> {
  const res = await fetch(`${API_BASE}/api/v1/admin/permissions/matrix`, { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load permission matrix"));
  return res.json();
}

export async function fetchRolesAudit(session: AuthSession): Promise<{ issues: Record<string, unknown>[]; summary: Record<string, number> }> {
  const res = await fetch(`${API_BASE}/api/v1/admin/roles/audit`, { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to run roles audit"));
  return res.json();
}

export async function fetchAdminContext(session: AuthSession): Promise<AdminContext> {
  const res = await fetch(`${API_BASE}/api/v1/admin/context`, { headers: adminHeaders(session) });
  if (res.status === 404) return DEFAULT_CONTEXT;
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
  const body: unknown = await res.json();
  if (Array.isArray(body)) {
    const items = body.map((row) => normalizeOrganization(row as Record<string, unknown>));
    return { items, counts: computeCounts(items) };
  }
  const wrapped = body as { items?: unknown[]; counts?: Record<string, number> };
  const items = (wrapped.items ?? []).map((row) =>
    normalizeOrganization(row as Record<string, unknown>),
  );
  return {
    items,
    counts: wrapped.counts ?? computeCounts(items),
  };
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
  const body = await res.json();
  return normalizeOrganization(body as Record<string, unknown>);
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
  const body = await res.json();
  return normalizeOrganization(body as Record<string, unknown>);
}

export async function fetchOrganizationDirectory(
  session: AuthSession,
  orgId: string,
  page: number,
  pageSize = 5,
  orgFallback?: AdminOrganization,
) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/directory?page=${page}&page_size=${pageSize}`,
    { headers: adminHeaders(session) },
  );
  if (res.ok) {
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
  if (res.status === 404) {
    const memRes = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/members`, {
      headers: adminHeaders(session),
    });
    if (!memRes.ok) throw new Error(await readApiError(res, "Failed to load members"));
    const members = (await memRes.json()) as {
      id: string;
      user_id: string;
      email: string;
      full_name: string;
      role: string;
      is_active: boolean;
      user_is_active: boolean;
    }[];
    const rows: DirectoryRow[] = members.map((m) => ({
      row_id: `m-${m.id}`,
      kind: "member" as const,
      membership_id: m.id,
      user_id: m.user_id,
      full_name: m.full_name,
      email: m.email,
      role: m.role,
      status: m.is_active && m.user_is_active ? "Active" : "Inactive",
    }));
    const total = rows.length;
    const start = (page - 1) * pageSize;
    const seats =
      orgFallback?.seats ??
      ({
        active_members: members.filter((m) => m.is_active).length,
        pending_invitations: 0,
        seats_used: members.filter((m) => m.is_active).length,
        seats_limit: orgFallback?.license_limit ?? 0,
        seats_available: 0,
        is_full: false,
      } as SeatUsage);
    return {
      seats,
      license_status: orgFallback?.license_status ?? "active",
      license_renews_at: orgFallback?.license_renews_at ?? null,
      rows: rows.slice(start, start + pageSize),
      total,
      page,
      page_size: pageSize,
    };
  }
  throw new Error(await readApiError(res, "Failed to load members"));
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
    invitation_setup_url: string;
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

export async function fetchAdminInvitationLink(session: AuthSession, orgId: string, invitationId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/invitations/admin/${invitationId}/link`,
    { headers: adminHeaders(session) },
  );
  if (!res.ok) await parseError(res, "Failed to load invitation link");
  return res.json() as Promise<{
    invitation_setup_path?: string;
    invitation_setup_url?: string;
    join_path?: string;
    join_url?: string;
    expires_at?: string;
  }>;
}

export async function deleteAdminInvitationRecord(session: AuthSession, orgId: string, invitationId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/invitations/admin/${invitationId}`,
    { method: "DELETE", headers: adminHeaders(session) },
  );
  if (!res.ok) await parseError(res, "Failed to delete invitation");
}

export async function fetchEmployeeLinkUrl(session: AuthSession, orgId: string, linkId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/employee-link/${linkId}/link`,
    { headers: adminHeaders(session) },
  );
  if (!res.ok) await parseError(res, "Failed to load employee link");
  return res.json() as Promise<{ join_path?: string; join_url?: string; expires_at?: string }>;
}

export async function deleteEmployeeLinkRecord(session: AuthSession, orgId: string, linkId: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/employee-link/${linkId}`,
    { method: "DELETE", headers: adminHeaders(session) },
  );
  if (!res.ok) await parseError(res, "Failed to delete employee link");
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

export async function deactivateMember(
  session: AuthSession,
  orgId: string,
  membershipId: string,
  reason: string,
) {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/organizations/${orgId}/members/${membershipId}/deactivate`,
    {
      method: "POST",
      headers: adminHeaders(session),
      body: JSON.stringify({ reason }),
    },
  );
  if (!res.ok) await parseError(res, "Failed to remove member");
}

export async function invitePlatformStaff(
  session: AuthSession,
  payload: { email: string; full_name: string; role: string },
): Promise<PlatformStaffMember> {
  const res = await fetch(`${API_BASE}/api/v1/admin/platform-staff/invite`, {
    method: "POST",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to invite platform user");
  return res.json();
}

export async function updatePlatformStaffRole(
  session: AuthSession,
  userId: string,
  payload: { role: string; reason: string },
): Promise<PlatformStaffMember> {
  const res = await fetch(`${API_BASE}/api/v1/admin/platform-staff/${userId}`, {
    method: "PATCH",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to update platform role");
  return res.json();
}

export type InvitationHistoryRow = {
  id: string;
  record_type: "admin_invitation" | "employee_link" | string;
  kind: string;
  email: string;
  role: string | null;
  status: string;
  invitee_full_name: string | null;
  expires_at: string | null;
  created_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  joined_count?: number | null;
  pending_approval_count?: number | null;
  invite_url?: string | null;
  invite_path?: string | null;
};

export type InvitationsSetupStatus = {
  admin_invitation_status: string;
  admin_invitation_email: string | null;
  admin_accepted: boolean;
  has_active_org_admin?: boolean;
  pending_org_admin_invite?: boolean;
  employee_link_status: string | null;
  employee_link_joined_count: number;
  employee_link_pending_count: number;
  seats: SeatUsage;
};

export type EmployeeLinkSummary = {
  link_id: string | null;
  status: string | null;
  joined_count: number;
  pending_approval_count: number;
  max_joins: number | null;
  expires_at: string | null;
  allowed_domains: string[];
  require_admin_approval: boolean;
};

export async function fetchInvitationsSetup(session: AuthSession, orgId: string) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/invitations/setup`, {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load setup status"));
  return res.json() as Promise<InvitationsSetupStatus>;
}

export async function fetchInvitationHistory(session: AuthSession, orgId: string, status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/invitations/history${q}`, {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load invitation history"));
  return res.json() as Promise<InvitationHistoryRow[]>;
}

export async function createAdminInvitation(
  session: AuthSession,
  orgId: string,
  payload: { email: string; full_name: string; personal_message?: string; expires_days?: number },
) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/invitations/admin`, {
    method: "POST",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to create admin invitation");
  return res.json() as Promise<{
    invitation_setup_path: string;
    invitation_setup_url: string;
    invitation_expires_at: string;
    email_sent: boolean;
  }>;
}

export async function fetchEmployeeLinkSummary(session: AuthSession, orgId: string) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/employee-link`, {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load employee link"));
  return res.json() as Promise<EmployeeLinkSummary>;
}

export async function createEmployeeLink(
  session: AuthSession,
  orgId: string,
  payload: {
    allowed_domains: string[];
    require_admin_approval?: boolean;
    max_joins?: number;
    expires_days?: number | null;
  },
) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/employee-link`, {
    method: "POST",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to create employee link");
  return res.json() as Promise<{ join_path: string; join_url: string; link_id: string; expires_at: string | null }>;
}

export async function rotateEmployeeLink(session: AuthSession, orgId: string, linkId: string) {
  const res = await fetch(`${API_BASE}/api/v1/admin/organizations/${orgId}/employee-link/${linkId}/rotate`, {
    method: "POST",
    headers: adminHeaders(session),
  });
  if (!res.ok) await parseError(res, "Failed to rotate link");
  return res.json() as Promise<{ join_path: string; join_url: string; expires_at?: string }>;
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
