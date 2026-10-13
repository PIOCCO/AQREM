import { readApiError } from "./errors";
import type { AuthSession } from "./api";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function headers(session: AuthSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Organization-Id": session.organizationId!,
    "Content-Type": "application/json",
  };
}

export type SetupStep = {
  id: string;
  title: string;
  status: string;
  detail: string;
};

export type SetupChecklist = {
  steps: SetupStep[];
  completed_count: number;
  total_count: number;
  incomplete_count: number;
  percent: number;
  employee_link_enabled: boolean;
  storage_configured: boolean;
  model_token_status: string;
};

export type OrgOverview = {
  organization: { id: string; name: string; license_limit: number; license_status: string };
  setup: SetupChecklist;
  seats: { used: number; limit: number; available: number; is_full: boolean };
  employee_link: { url_path: string; enabled: boolean };
};

export async function recordAdminConsoleEnter(session: AuthSession): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/console-enter`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Admin console access denied"));
}

export async function fetchOrgOverview(session: AuthSession): Promise<OrgOverview> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/overview`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load overview"));
  return res.json();
}

export async function fetchDocuments(session: AuthSession, page = 1, pageSize = 10) {
  const res = await fetch(
    `${API_BASE}/api/v1/org-admin/documents?page=${page}&page_size=${pageSize}`,
    { headers: headers(session) },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load documents"));
  return res.json();
}

export async function uploadDocuments(session: AuthSession, files: FileList | File[]) {
  const form = new FormData();
  for (const f of Array.from(files)) form.append("files", f);
  const res = await fetch(`${API_BASE}/api/v1/org-admin/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.token}`, "X-Organization-Id": session.organizationId! },
    body: form,
  });
  if (!res.ok) throw new Error(await readApiError(res, "Upload failed"));
  return res.json();
}

export async function removeDocument(session: AuthSession, documentId: string) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/documents/${documentId}`, {
    method: "DELETE",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Remove failed"));
}

export async function retryDocument(session: AuthSession, documentId: string) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/documents/${documentId}/retry`, {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Retry failed"));
  return res.json();
}

export type ModelTokenInfo = {
  masked_value: string;
  status: string;
  expires_at: string | null;
  last_rotated_at: string | null;
  last_test_at: string | null;
  last_test_status: string | null;
  expiry_warning_days: number | null;
};

export async function fetchModelToken(session: AuthSession): Promise<ModelTokenInfo> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/model-token`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load model token status"));
  return res.json();
}

export async function saveModelToken(session: AuthSession, token: string) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/model-token`, {
    method: "PUT",
    headers: headers(session),
    body: JSON.stringify({ token }),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to save token"));
  return res.json() as Promise<ModelTokenInfo>;
}

export async function testModelToken(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/model-token/test`, {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Connection test failed"));
  return res.json() as Promise<{ success: boolean; message: string }>;
}

export async function fetchMembers(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/members`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load members"));
  return res.json();
}

export async function inviteMember(
  session: AuthSession,
  payload: { email: string; full_name: string; role: string },
) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/members/invite`, {
    method: "POST",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Invite failed"));
  return res.json();
}

export async function fetchOrgUsage(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/usage`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load usage"));
  return res.json();
}

export async function fetchOrgAudit(session: AuthSession, limit = 50) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/audit?limit=${limit}`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load audit log"));
  return res.json();
}

export async function fetchChatSharing(session: AuthSession): Promise<{ enabled: boolean; default_ttl_days: number }> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/chat-sharing`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load chat sharing settings"));
  return res.json();
}

export async function updateChatSharing(
  session: AuthSession,
  payload: { enabled: boolean; default_ttl_days?: number },
): Promise<{ enabled: boolean; default_ttl_days: number }> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/chat-sharing`, {
    method: "PUT",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to update chat sharing"));
  return res.json();
}

export async function fetchTelemetrySchema(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/telemetry-schema`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load telemetry schema"));
  return res.json();
}

export async function recordEmployeeLinkCopied(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/employee-link/copied`, {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Could not record link copy"));
}

export type DataStorageConfig = {
  storage_mode: string;
  connection_method: string;
  status: string;
  host: string | null;
  port: number | null;
  database_name: string | null;
  schema_name: string;
  ssl_mode: string;
  username: string | null;
  has_credentials: boolean;
  schema_version: number;
  last_health_status: string | null;
  last_health_summary: string | null;
  last_latency_ms: number | null;
  last_health_check_at: string | null;
  paused: boolean;
};

export type PreflightCheck = { id: string; title: string; status: string; detail: string };

export type PreflightReport = { ok: boolean; latency_ms?: number | null; checks: PreflightCheck[] };

export type DataStoragePayload = {
  storage_mode: string;
  connection_method?: string;
  host?: string | null;
  port?: number | null;
  database_name?: string | null;
  schema_name?: string;
  ssl_mode?: string;
  username?: string | null;
  password?: string | null;
};

export async function fetchDataStorage(session: AuthSession): Promise<DataStorageConfig> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/data-storage`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load data storage"));
  return res.json();
}

export async function runDataStoragePreflight(
  session: AuthSession,
  payload: DataStoragePayload,
): Promise<PreflightReport> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/data-storage/preflight`, {
    method: "POST",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Preflight request failed"));
  return res.json();
}

export async function configureDataStorage(
  session: AuthSession,
  payload: DataStoragePayload,
): Promise<DataStorageConfig> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/data-storage`, {
    method: "PUT",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to save data storage"));
  return res.json();
}
