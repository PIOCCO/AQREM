import { apiErrorMessage, readApiError, readResponseJson } from "./errors";
import type { AuthSession } from "./api";
import { resolveApiBase } from "./apiBase";

function apiUrl(path: string): string {
  const base = resolveApiBase();
  return `${base}${path}`;
}



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
  deletion_status?: string;
  purge_scheduled_at?: string | null;
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
  /** False or missing when the API on :8000 is an older build without soft delete routes. */
  organization_soft_delete?: boolean;
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
  const s = status.trim().toLowerCase();
  if (s === "test") return "test";
  if (s === "expired") return "expired";
  if (s === "suspended") return "suspended";
  return "active";
}

function isDeleteOrganizationResponse(body: unknown): body is {
  organization_id: string;
  purge_scheduled_at: string;
  retention_days: number;
} {
  if (!body || typeof body !== "object") return false;
  const row = body as Record<string, unknown>;
  const orgId = row.organization_id ?? row.organizationId;
  const purgeAt = row.purge_scheduled_at ?? row.purgeScheduledAt;
  const retention = row.retention_days ?? row.retentionDays;
  return (
    (typeof orgId === "string" || typeof orgId === "number") &&
    typeof purgeAt === "string" &&
    typeof retention === "number" &&
    !("seats" in row)
  );
}

const adminFetchInit: RequestInit = { cache: "no-store" };

function computeCounts(items: AdminOrganization[]): Record<string, number> {
  const counts = { all: 0, active: 0, suspended: 0, expired: 0, test: 0, pending_deletion: 0 };
  for (const o of items) {
    if (o.deletion_status === "pending_deletion") {
      counts.pending_deletion += 1;
      continue;
    }
    counts.all += 1;
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
    deletion_status: (raw.deletion_status as string | undefined) ?? "active",
    purge_scheduled_at: (raw.purge_scheduled_at as string | null) ?? null,
    seats,
  };
}

export async function restoreAdminOrganization(session: AuthSession, orgId: string): Promise<AdminOrganization> {
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/restore`), {
    method: "POST",
    headers: adminHeaders(session),
  });
  if (!res.ok) await parseError(res, "Failed to restore organization");
  const body = await res.json();
  return normalizeOrganization(body as Record<string, unknown>);
}

export async function purgeAdminOrganizationNow(
  session: AuthSession,
  orgId: string,
  confirmName: string,
): Promise<void> {
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/purge-now`), {
    method: "POST",
    headers: adminHeaders(session),
    body: JSON.stringify({ confirmName }),
  });
  if (!res.ok) await parseError(res, "Failed to purge organization");
}

export async function deleteAdminOrganization(
  session: AuthSession,
  orgId: string,
  confirmName: string,
): Promise<{ organization_id: string; purge_scheduled_at: string; retention_days: number }> {
  const body = JSON.stringify({ confirmName: confirmName });
  const headers = adminHeaders(session);
  const apiBase = resolveApiBase() || "(same origin)";
  const attempts: { method: string; path: string; body?: string }[] = [
    { method: "POST", path: `/api/v1/admin/organizations/${orgId}/delete`, body },
    { method: "POST", path: `/api/v1/admin/organizations/${orgId}/schedule-deletion`, body },
    { method: "DELETE", path: `/api/v1/admin/organizations/${orgId}`, body },
  ];
  const attemptLog: string[] = [];
  let last: Response | null = null;
  for (const attempt of attempts) {
    const url = apiUrl(attempt.path);
    last = await fetch(url, {
      ...adminFetchInit,
      method: attempt.method,
      headers,
      body: attempt.body,
    });
    if (last.ok) {
      const payload: unknown = await last.json();
      if (isDeleteOrganizationResponse(payload)) {
        const row = payload as Record<string, unknown>;
        return {
          organization_id: String(row.organization_id ?? row.organizationId),
          purge_scheduled_at: String(row.purge_scheduled_at ?? row.purgeScheduledAt),
          retention_days: Number(row.retention_days ?? row.retentionDays),
        };
      }
      attemptLog.push(`${attempt.method} ${attempt.path} → ${last.status} (organization payload, not a delete result)`);
      continue;
    }
    attemptLog.push(`${attempt.method} ${attempt.path} → ${last.status}`);
    if (last.status !== 404 && last.status !== 405) {
      await parseError(last, "Failed to delete organization");
    }
  }
  const detail = attemptLog.length ? attemptLog.join("; ") : "no endpoints responded";
  throw new Error(
    `Organization delete is not available on the API at ${apiBase}. ${detail}. ` +
      "Stop and restart the backend on port 8000 from the latest AQREM branch (POST …/delete or …/schedule-deletion must return purge_scheduled_at). " +
      "The UI at :5173 calls that host for API requests — updating only the frontend is not enough.",
  );
}

export async function fetchPlatformStaff(session: AuthSession): Promise<PlatformStaffMember[]> {
  const res = await fetch(apiUrl(`/api/v1/admin/platform-staff`), { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load platform team"));
  return res.json();
}

export async function fetchPermissionsMatrix(session: AuthSession): Promise<PermissionsMatrix> {
  const res = await fetch(apiUrl(`/api/v1/admin/permissions/matrix`), { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load permission matrix"));
  return res.json();
}

export async function fetchRolesAudit(session: AuthSession): Promise<{ issues: Record<string, unknown>[]; summary: Record<string, number> }> {
  const res = await fetch(apiUrl(`/api/v1/admin/roles/audit`), { headers: adminHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to run roles audit"));
  return res.json();
}

export async function fetchAdminContext(session: AuthSession): Promise<AdminContext> {
  const res = await fetch(apiUrl(`/api/v1/admin/context`), { headers: adminHeaders(session) });
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations?${qs}`), {
    ...adminFetchInit,
    headers: adminHeaders(session),
  });
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations`), {
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}`), {
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
  _orgFallback?: AdminOrganization,
) {
  const res = await fetch(
    apiUrl(`/api/v1/admin/organizations/${orgId}/directory?page=${page}&page_size=${pageSize}`),
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
  throw new Error(await readApiError(res, "Failed to load organization directory"));
}

export async function inviteOrganizationUser(
  session: AuthSession,
  orgId: string,
  payload: { email: string; full_name: string; role: string },
) {
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/users`), {
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
    apiUrl(`/api/v1/admin/organizations/${orgId}/invitations/${invitationId}/resend`),
    { method: "POST", headers: adminHeaders(session) },
  );
  if (!res.ok) await parseError(res, "Failed to resend invitation");
  return res.json();
}

export async function fetchAdminInvitationLink(session: AuthSession, orgId: string, invitationId: string) {
  const res = await fetch(
    apiUrl(`/api/v1/admin/organizations/${orgId}/invitations/admin/${invitationId}/link`),
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

async function deleteWithPostOnly(
  urls: string[],
  session: AuthSession,
): Promise<Response> {
  const headers = adminHeaders(session);
  let last: Response | null = null;
  for (const url of urls) {
    last = await fetch(url, { method: "POST", headers });
    if (last.ok || (last.status !== 404 && last.status !== 405)) {
      return last;
    }
  }
  return last ?? new Response(null, { status: 404 });
}

export async function deleteAdminInvitationRecord(session: AuthSession, orgId: string, invitationId: string) {
  const res = await deleteWithPostOnly(
    [
      apiUrl(`/api/v1/admin/organizations/${orgId}/invitations/admin/${invitationId}/delete`),
      apiUrl(`/api/v1/admin/organizations/${orgId}/invitation-history/${invitationId}/delete`),
    ],
    session,
  );
  if (!res.ok) {
    await parseError(
      res,
      "Failed to delete invitation history — update the backend on port 8000 (revoke alone does not remove history rows).",
    );
  }
}

export async function fetchEmployeeLinkUrl(session: AuthSession, orgId: string, linkId: string) {
  const res = await fetch(
    apiUrl(`/api/v1/admin/organizations/${orgId}/employee-link/${linkId}/link`),
    { headers: adminHeaders(session) },
  );
  if (!res.ok) await parseError(res, "Failed to load employee link");
  return res.json() as Promise<{ join_path?: string; join_url?: string; expires_at?: string }>;
}

export async function deleteEmployeeLinkRecord(session: AuthSession, orgId: string, linkId: string) {
  const res = await deleteWithPostOnly(
    [
      apiUrl(`/api/v1/admin/organizations/${orgId}/employee-link/${linkId}/delete`),
      apiUrl(`/api/v1/admin/organizations/${orgId}/invitation-history/${linkId}/delete`),
    ],
    session,
  );
  if (!res.ok) await parseError(res, "Failed to delete employee link");
}

export async function revokeInvitation(session: AuthSession, orgId: string, invitationId: string) {
  const res = await fetch(
    apiUrl(`/api/v1/admin/organizations/${orgId}/invitations/${invitationId}/revoke`),
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/members/${membershipId}`), {
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
    apiUrl(`/api/v1/admin/organizations/${orgId}/members/${membershipId}/deactivate`),
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
  const res = await fetch(apiUrl(`/api/v1/admin/platform-staff/invite`), {
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
  const res = await fetch(apiUrl(`/api/v1/admin/platform-staff/${userId}`), {
    method: "PATCH",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to update platform role");
  return res.json();
}

export function invitationHistoryRecordType(row: InvitationHistoryRow): "admin_invitation" | "employee_link" {
  const rt = (row.record_type ?? "").toLowerCase();
  if (rt === "employee_link" || row.kind === "employee_link") return "employee_link";
  if (rt === "admin_invitation" || row.kind === "org_admin") return "admin_invitation";
  if (row.email?.startsWith("Employee link")) return "employee_link";
  return "admin_invitation";
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/invitations/setup`), {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load setup status"));
  return res.json() as Promise<InvitationsSetupStatus>;
}

export async function fetchInvitationHistory(session: AuthSession, orgId: string, status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/invitations/history${q}`), {
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/invitations/admin`), {
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/employee-link`), {
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
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/employee-link`), {
    method: "POST",
    headers: adminHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to create employee link");
  return res.json() as Promise<{ join_path: string; join_url: string; link_id: string; expires_at: string | null }>;
}

export async function rotateEmployeeLink(session: AuthSession, orgId: string, linkId: string) {
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/employee-link/${linkId}/rotate`), {
    method: "POST",
    headers: adminHeaders(session),
  });
  if (!res.ok) await parseError(res, "Failed to rotate link");
  return res.json() as Promise<{ join_path: string; join_url: string; expires_at?: string }>;
}

export async function fetchOrgInvitations(session: AuthSession, orgId: string) {
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/invitations`), {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load invitations"));
  return res.json();
}

export async function fetchOrgAudit(session: AuthSession, orgId: string) {
  const res = await fetch(apiUrl(`/api/v1/admin/organizations/${orgId}/audit`), {
    headers: adminHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load audit log"));
  return res.json() as Promise<{ items: { id: string; created_at: string; actor_email: string; action: string; target: string }[] }>;
}

export function isAdminApiError(e: unknown): e is Error & { admin: AdminApiError } {
  return e instanceof Error && "admin" in e && typeof (e as { admin?: AdminApiError }).admin?.code === "string";
}
