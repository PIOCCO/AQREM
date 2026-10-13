import type { AuthSession } from "./api";
import { readApiError } from "./errors";

function authHeaders(session: AuthSession): HeadersInit {
  const h: Record<string, string> = { Authorization: `Bearer ${session.token}` };
  if (session.organizationId) h["X-Organization-Id"] = session.organizationId;
  return h;
}

async function activityFetch(session: AuthSession, url: string): Promise<Response> {
  const res = await fetch(url, { headers: authHeaders(session) });
  return res;
}

export type ActivityEvent = {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  created_at: string;
  actor_user_id?: string | null;
  actor_name: string;
  actor_email?: string | null;
  actor_deleted_id?: string | null;
  target_label?: string | null;
  summary: string;
  category: string;
  secondary: string;
  action_group: string;
  is_security: boolean;
  is_failure: boolean;
  result: string;
  ip_address?: string | null;
  user_agent?: string | null;
  request_id?: string | null;
  changes?: Record<string, unknown> | null;
  metadata_safe?: Record<string, unknown>;
};

export type ActivityQuery = {
  offset?: number;
  limit?: number;
  search?: string;
  actions?: string[];
  actor_user_id?: string[];
  date_from?: string;
  date_to?: string;
  sort?: "newest" | "oldest";
};

export type ActivityListResponse = {
  items: ActivityEvent[];
  total: number;
  offset: number;
  limit: number;
  next_offset?: number | null;
};

export type ActivityActor = { user_id: string; name: string; email: string };

function qs(params: ActivityQuery): string {
  const sp = new URLSearchParams();
  if (params.offset != null) sp.set("offset", String(params.offset));
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.search) sp.set("search", params.search);
  if (params.sort) sp.set("sort", params.sort);
  if (params.date_from) sp.set("date_from", params.date_from);
  if (params.date_to) sp.set("date_to", params.date_to);
  params.actions?.forEach((a) => sp.append("actions", a));
  params.actor_user_id?.forEach((id) => sp.append("actor_user_id", id));
  return sp.toString();
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchActivity(session: AuthSession, query: ActivityQuery): Promise<ActivityListResponse> {
  const res = await activityFetch(session, `${API_BASE}/api/v1/audit?${qs(query)}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load activity"));
  return res.json();
}

export async function fetchActivityActors(session: AuthSession): Promise<ActivityActor[]> {
  const res = await activityFetch(session, `${API_BASE}/api/v1/audit/actors`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load actors"));
  const data = await res.json();
  return data.items ?? [];
}

export async function exportActivity(
  session: AuthSession,
  format: "csv" | "json",
  query: ActivityQuery,
): Promise<Blob> {
  const sp = new URLSearchParams(qs(query));
  sp.set("format", format);
  const res = await activityFetch(session, `${API_BASE}/api/v1/audit/export?${sp.toString()}`);
  if (!res.ok) throw new Error(await readApiError(res, "Export failed"));
  return res.blob();
}
