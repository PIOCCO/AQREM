import { readApiError } from "./errors";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type AuthSession = {
  token: string;
  organizationId: string;
};

function authHeaders(session: AuthSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Organization-Id": session.organizationId,
    "Content-Type": "application/json",
  };
}

export async function registerUser(payload: {
  email: string;
  password: string;
  full_name: string;
  organization_name: string;
}) {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Registration failed");
  return res.json();
}

export async function loginUser(payload: { email: string; password: string }) {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Login failed");
  return res.json();
}

export async function fetchMetrics(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/metrics`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to load metrics");
  return res.json();
}

export async function fetchQuestionnaires(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires`, { headers: authHeaders(session) });
  if (!res.ok) throw new Error("Failed to load questionnaires");
  return res.json();
}

export async function fetchQuestionnaireQuestions(
  session: AuthSession,
  questionnaireId: string,
  params?: { status?: string; search?: string },
) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.search) qs.set("search", params.search);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/${questionnaireId}/questions${suffix}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load questions"));
  return res.json();
}

export async function fetchQuestionDetail(session: AuthSession, questionId: string) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/questions/${questionId}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to load question");
  return res.json();
}

export async function generateQuestionnaireAnswers(session: AuthSession, questionnaireId: string) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/${questionnaireId}/generate`, {
    method: "POST",
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Unable to generate answers. Please try again."));
  return res.json();
}

export async function approveAnswer(session: AuthSession, answerId: string) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/answers/${answerId}/approve`, {
    method: "POST",
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to approve answer");
  return res.json();
}

export async function rejectAnswer(session: AuthSession, answerId: string) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/answers/${answerId}/reject`, {
    method: "POST",
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to reject answer");
  return res.json();
}

export async function editAnswer(session: AuthSession, answerId: string, text: string) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/answers/${answerId}/edit`, {
    method: "POST",
    headers: authHeaders(session),
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("Failed to edit answer");
  return res.json();
}

export function loadSession(): AuthSession | null {
  const token = localStorage.getItem("aqrem_token");
  const organizationId = localStorage.getItem("aqrem_org");
  if (!token || !organizationId) return null;
  return { token, organizationId };
}

export function saveSession(token: string, organizationId: string) {
  localStorage.setItem("aqrem_token", token);
  localStorage.setItem("aqrem_org", organizationId);
}

export function clearSession() {
  localStorage.removeItem("aqrem_token");
  localStorage.removeItem("aqrem_org");
}

export async function fetchProjects(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/projects`, { headers: authHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load projects"));
  return res.json();
}

export async function fetchProjectSummaries(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/projects/summaries`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load project summaries"));
  return res.json();
}

export async function createProject(session: AuthSession, payload: { name: string; description?: string }) {
  const res = await fetch(`${API_BASE}/api/v1/projects`, {
    method: "POST",
    headers: authHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to create project"));
  return res.json();
}

export async function fetchSources(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/sources`, { headers: authHeaders(session) });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load sources"));
  return res.json();
}

export async function fetchEvidence(
  session: AuthSession,
  params?: { project_id?: string; source_id?: string; search?: string; offset?: number; limit?: number },
) {
  const qs = new URLSearchParams();
  if (params?.project_id) qs.set("project_id", params.project_id);
  if (params?.source_id) qs.set("source_id", params.source_id);
  if (params?.search) qs.set("search", params.search);
  if (params?.offset != null) qs.set("offset", String(params.offset));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const res = await fetch(`${API_BASE}/api/v1/evidence?${qs.toString()}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load evidence"));
  return res.json();
}

export async function fetchEvidenceDetail(session: AuthSession, evidenceId: string) {
  const res = await fetch(`${API_BASE}/api/v1/evidence/${evidenceId}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load evidence detail"));
  return res.json();
}

export async function fetchDashboardOverview(session: AuthSession, projectId?: string | null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await fetch(`${API_BASE}/api/v1/dashboard/overview${qs}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Unable to load dashboard"));
  return res.json();
}

export async function fetchReviewQueue(
  session: AuthSession,
  params?: { project_id?: string; search?: string; offset?: number; limit?: number },
) {
  const qs = new URLSearchParams();
  if (params?.project_id) qs.set("project_id", params.project_id);
  if (params?.search) qs.set("search", params.search);
  if (params?.offset != null) qs.set("offset", String(params.offset));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const res = await fetch(`${API_BASE}/api/v1/review-queue?${qs.toString()}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load review queue"));
  return res.json();
}

export async function fetchAuditLog(session: AuthSession, offset = 0, limit = 50) {
  const res = await fetch(`${API_BASE}/api/v1/audit?offset=${offset}&limit=${limit}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load activity log"));
  return res.json();
}

export async function fetchQuestionnaire(session: AuthSession, questionnaireId: string) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/${questionnaireId}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load questionnaire"));
  return res.json();
}

export async function downloadQuestionnaireExport(
  session: AuthSession,
  questionnaireId: string,
  format: "csv" | "xlsx",
  options?: { approved_only?: boolean },
) {
  const qs = new URLSearchParams();
  if (options?.approved_only) qs.set("approved_only", "true");
  const res = await fetch(
    `${API_BASE}/api/v1/questionnaires/${questionnaireId}/export/${format}?${qs.toString()}`,
    { headers: { Authorization: `Bearer ${session.token}`, "X-Organization-Id": session.organizationId } },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Export failed"));
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? `questionnaire.${format}`;
  return { blob, filename };
}

export async function fetchAnswerLibrary(session: AuthSession, query?: string) {
  const res = await fetch(`${API_BASE}/api/v1/answer-library/search`, {
    method: "POST",
    headers: authHeaders(session),
    body: JSON.stringify({ query, limit: 50 }),
  });
  if (!res.ok) throw new Error("Failed to load answer library");
  return res.json();
}

export async function fetchAnswerLibraryEntry(session: AuthSession, entryId: string) {
  const res = await fetch(`${API_BASE}/api/v1/answer-library/${entryId}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to load library entry");
  return res.json();
}

export async function fetchStaleAnswers(
  session: AuthSession,
  params?: { search?: string; project_id?: string; offset?: number; limit?: number },
) {
  const qs = new URLSearchParams();
  if (params?.search) qs.set("search", params.search);
  if (params?.project_id) qs.set("project_id", params.project_id);
  if (params?.offset != null) qs.set("offset", String(params.offset));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const res = await fetch(`${API_BASE}/api/v1/stale-answers?${qs.toString()}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to load stale answers");
  return res.json();
}

export async function fetchStaleAnswerDetail(session: AuthSession, answerId: string) {
  const res = await fetch(`${API_BASE}/api/v1/stale-answers/${answerId}`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to load stale answer detail");
  return res.json();
}

export async function revalidateStaleAnswer(session: AuthSession, answerId: string) {
  const res = await fetch(`${API_BASE}/api/v1/stale-answers/${answerId}/revalidate`, {
    method: "POST",
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Revalidation failed");
  return res.json();
}

export async function regenerateStaleAnswer(session: AuthSession, answerId: string) {
  const res = await fetch(`${API_BASE}/api/v1/stale-answers/${answerId}/regenerate`, {
    method: "POST",
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Regeneration failed");
  return res.json();
}

export async function validateLibraryEntry(session: AuthSession, entryId: string) {
  const res = await fetch(`${API_BASE}/api/v1/answer-library/${entryId}/validation`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to validate library entry");
  return res.json();
}
