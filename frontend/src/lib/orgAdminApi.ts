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
  percent: number;
  ai_provider_status: string;
  storage_configured: boolean;
};

export async function fetchOrgSetup(session: AuthSession): Promise<SetupChecklist> {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/setup`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load setup checklist"));
  return res.json();
}

export async function fetchOrgOverview(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/org-admin/overview`, { headers: headers(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load overview"));
  return res.json();
}
