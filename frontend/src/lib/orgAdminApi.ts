import { resolveApiBase } from "./apiBase";

function apiUrl(p: string) { return `${resolveApiBase()}${p}`; }

import { readApiError, readApiErrorDetail } from "./errors";
import type { AuthSession } from "./api";


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
  postgres_database_status: string;
};

export type OrgOverview = {
  organization: { id: string; name: string; license_limit: number; license_status: string };
  setup: SetupChecklist;
  seats: { used: number; limit: number; available: number; is_full: boolean };
  employee_link: { url_path: string; enabled: boolean };
};

export async function recordAdminConsoleEnter(session: AuthSession): Promise<void> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/console-enter`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Admin console access denied"));
}

export async function fetchOrgOverview(session: AuthSession): Promise<OrgOverview> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/overview`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load overview"));
  return res.json();
}

export async function fetchAccessGroups(session: AuthSession) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/access/groups`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load groups"));
  return res.json() as Promise<
    Array<{ id: string; name: string; slug: string; is_system: boolean; member_count: number }>
  >;
}

export async function fetchDocumentsNeedingReview(session: AuthSession) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/access/documents/needs-review/count`), {
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load review count"));
  return res.json() as Promise<{ count: number }>;
}

export async function fetchDocuments(session: AuthSession, page = 1, pageSize = 10) {
  const res = await fetch(
    apiUrl(`/api/v1/org-admin/documents?page=${page}&page_size=${pageSize}`),
    { headers: headers(session) },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load documents"));
  return res.json();
}

const UPLOAD_TIMEOUT_MS = 120_000;

export async function uploadDocuments(
  session: AuthSession,
  files: FileList | File[],
  visibilityMode: string,
  visibilityGroupIds?: string[],
) {
  const form = new FormData();
  for (const f of Array.from(files)) form.append("files", f);
  form.append("visibility_mode", visibilityMode);
  if (visibilityGroupIds?.length) {
    form.append("visibility_group_ids", visibilityGroupIds.join(","));
  }
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);
  try {
    const res = await fetch(apiUrl(`/api/v1/org-admin/documents/upload`), {
      method: "POST",
      headers: { Authorization: `Bearer ${session.token}`, "X-Organization-Id": session.organizationId! },
      body: form,
      signal: controller.signal,
    });
    if (!res.ok) {
      const { message, code } = await readApiErrorDetail(res, "Upload failed");
      const err = new Error(message) as Error & { code?: string };
      err.code = code;
      throw err;
    }
    return res.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Upload timed out after 2 minutes. Try a smaller file or check API and storage health.");
    }
    throw err;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function removeDocument(session: AuthSession, documentId: string) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/documents/${documentId}`), {
    method: "DELETE",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Remove failed"));
  if (res.status !== 204) {
    await res.json().catch(() => null);
  }
}

export async function retryDocument(session: AuthSession, documentId: string) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/documents/${documentId}/retry`), {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Retry failed"));
  return res.json();
}

export async function fetchMembers(session: AuthSession) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/members`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load members"));
  return res.json();
}

export async function inviteMember(
  session: AuthSession,
  payload: { email: string; full_name: string; role: string },
) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/members/invite`), {
    method: "POST",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Invite failed"));
  return res.json();
}

export async function removeOrgMember(session: AuthSession, membershipId: string) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/members/${membershipId}/deactivate`), {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to remove member"));
}

export async function fetchOrgUsage(session: AuthSession) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/usage`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load usage"));
  return res.json();
}

export type OrgAuditRow = {
  id: string;
  created_at: string;
  action: string;
  resource_type: string;
  actor_email: string | null;
};

export type OrgAuditList = {
  items: OrgAuditRow[];
  total: number;
  page: number;
  page_size: number;
};

function normalizeOrgAuditList(raw: unknown, page: number, pageSize: number): OrgAuditList {
  if (Array.isArray(raw)) {
    return {
      items: raw as OrgAuditRow[],
      total: raw.length,
      page: 1,
      page_size: raw.length || pageSize,
    };
  }
  if (raw && typeof raw === "object") {
    const body = raw as Partial<OrgAuditList> & { rows?: OrgAuditRow[] };
    const items = body.items ?? body.rows ?? [];
    return {
      items,
      total: typeof body.total === "number" ? body.total : items.length,
      page: typeof body.page === "number" ? body.page : page,
      page_size: typeof body.page_size === "number" ? body.page_size : pageSize,
    };
  }
  return { items: [], total: 0, page, page_size: pageSize };
}

export async function fetchOrgAudit(session: AuthSession, page = 1, pageSize = 50): Promise<OrgAuditList> {
  const res = await fetch(
    apiUrl(`/api/v1/org-admin/audit?page=${page}&page_size=${pageSize}`),
    { headers: headers(session) },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load audit log"));
  const raw = await res.json();
  return normalizeOrgAuditList(raw, page, pageSize);
}

export async function cleanupOrgAuditLogs(
  session: AuthSession,
  scope: "older_than_7d" | "older_than_30d" | "all",
): Promise<{ deleted_count: number; scope: string }> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/audit-logs?scope=${encodeURIComponent(scope)}`), {
    method: "DELETE",
    headers: {
      ...headers(session),
      "X-Requested-With": "AQREM",
    },
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to clean up audit logs"));
  return res.json();
}

export async function downloadOrgAuditCsv(session: AuthSession): Promise<void> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/audit/export`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to export audit log"));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "audit-log.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export async function fetchChatSharing(session: AuthSession): Promise<{ enabled: boolean; default_ttl_days: number }> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/chat-sharing`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load chat sharing settings"));
  return res.json();
}

export async function updateChatSharing(
  session: AuthSession,
  payload: { enabled: boolean; default_ttl_days?: number },
): Promise<{ enabled: boolean; default_ttl_days: number }> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/chat-sharing`), {
    method: "PUT",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to update chat sharing"));
  return res.json();
}

export async function fetchTelemetrySchema(session: AuthSession) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/telemetry-schema`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load telemetry schema"));
  return res.json();
}

export async function recordEmployeeLinkCopied(session: AuthSession) {
  const res = await fetch(apiUrl(`/api/v1/org-admin/employee-link/copied`), {
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
  setup_validated_at: string | null;
  setup_complete: boolean;
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
  const res = await fetch(apiUrl(`/api/v1/org-admin/data-storage`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load data storage"));
  return res.json();
}

export async function runDataStoragePreflight(
  session: AuthSession,
  payload: DataStoragePayload,
): Promise<PreflightReport> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/data-storage/preflight`), {
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
  const res = await fetch(apiUrl(`/api/v1/org-admin/data-storage`), {
    method: "PUT",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to save data storage"));
  return res.json();
}

export async function refreshDataStorageHealth(session: AuthSession): Promise<DataStorageConfig> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/data-storage/refresh-health`), {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Health refresh failed"));
  return res.json();
}

export type AiCheck = { ok: boolean; code?: string; message: string };

export type AiConnectionTest = {
  ok: boolean;
  provider: string;
  error?: string;
  endpoint_host?: string;
  chat_deployment?: string;
  embedding_deployment?: string;
  embedding_dimensions?: number;
  chat?: AiCheck;
  embeddings?: AiCheck;
};

export type AiStatus = {
  provider: string;
  configured: boolean;
  endpoint?: string;
  chat_deployment?: string;
  embedding_deployment?: string;
  chat_model?: string;
  embedding_model?: string;
  dimensions?: number;
  mismatched_documents: string[];
  stale_chunks: number;
  vector_column_issues: string[];
  embedding_warning: string | null;
};

export async function fetchAiStatus(session: AuthSession): Promise<AiStatus> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/ai/status`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load AI status"));
  return res.json();
}

export async function testAiConnection(session: AuthSession): Promise<AiConnectionTest> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/ai/test-connection`), {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "AI connection test failed"));
  return res.json();
}

export async function reindexAllDocuments(
  session: AuthSession,
): Promise<{ queued: number; skipped_in_progress: number }> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/documents/reindex-all`), {
    method: "POST",
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Re-index failed"));
  return res.json();
}

export type ChatStrictness = "strict" | "balanced";

export async function fetchChatGuardrails(
  session: AuthSession,
): Promise<{ strictness: ChatStrictness; levels: ChatStrictness[]; min_relevance_score: number }> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/chat-guardrails`), { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load chat guardrail settings"));
  return res.json();
}

export async function updateChatGuardrails(
  session: AuthSession,
  payload: { strictness: ChatStrictness },
): Promise<{ strictness: ChatStrictness; levels: ChatStrictness[] }> {
  const res = await fetch(apiUrl(`/api/v1/org-admin/chat-guardrails`), {
    method: "PUT",
    headers: headers(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to update chat guardrails"));
  return res.json();
}
