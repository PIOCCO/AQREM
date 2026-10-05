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

/** Clear session and send user to login (invalid/expired JWT). */
export function handleUnauthorized(): void {
  clearSession();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.assign("/login?expired=1");
  }
}

export async function fetchAuthMe(session: AuthSession) {
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, { headers: authHeaders(session) });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Session expired");
  }
  if (!res.ok) throw new Error(await readApiError(res, "Failed to validate session"));
  return res.json();
}

function authOnlyHeaders(session: AuthSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Organization-Id": session.organizationId,
  };
}

async function authedFetch(session: AuthSession, url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, {
    ...init,
    headers: { ...authHeaders(session), ...(init?.headers as Record<string, string> | undefined) },
  });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Session expired");
  }
  return res;
}

async function authedFormFetch(session: AuthSession, url: string, form: FormData, method = "POST") {
  const res = await fetch(url, { method, headers: authOnlyHeaders(session), body: form });
  if (res.status === 401) {
    handleUnauthorized();
    throw new Error("Session expired");
  }
  return res;
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
  const res = await authedFetch(session, `${API_BASE}/api/v1/dashboard/metrics`);
  if (!res.ok) throw new Error("Failed to load metrics");
  return res.json();
}

export async function fetchQuestionnaires(session: AuthSession, projectId?: string | null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires${qs}`);
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
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires/${questionnaireId}/questions${suffix}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load questions"));
  return res.json();
}

export async function fetchQuestionDetail(session: AuthSession, questionId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires/questions/${questionId}`);
  if (!res.ok) throw new Error("Failed to load question");
  return res.json();
}

export async function generateQuestionnaireAnswers(session: AuthSession, questionnaireId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires/${questionnaireId}/generate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await readApiError(res, "Unable to generate answers. Please try again."));
  return res.json();
}

export async function approveAnswer(session: AuthSession, answerId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires/answers/${answerId}/approve`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to approve answer");
  return res.json();
}

export async function rejectAnswer(session: AuthSession, answerId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires/answers/${answerId}/reject`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to reject answer");
  return res.json();
}

export async function editAnswer(session: AuthSession, answerId: string, text: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires/answers/${answerId}/edit`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("Failed to edit answer");
  return res.json();
}

export async function fetchProjects(session: AuthSession) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/projects`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load projects"));
  return res.json();
}

export async function fetchProjectSummaries(session: AuthSession) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/projects/summaries`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load project summaries"));
  return res.json();
}

export async function createProject(session: AuthSession, payload: { name: string; description?: string }) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/projects`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to create project"));
  return res.json();
}

export async function fetchSources(session: AuthSession, projectId?: string | null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await authedFetch(session, `${API_BASE}/api/v1/sources${qs}`);
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
  const res = await authedFetch(session, `${API_BASE}/api/v1/evidence?${qs.toString()}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load evidence"));
  return res.json();
}

export async function fetchEvidenceDetail(session: AuthSession, evidenceId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/evidence/${evidenceId}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load evidence detail"));
  return res.json();
}

export async function fetchDashboardOverview(session: AuthSession, projectId?: string | null) {
  const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  const res = await authedFetch(session, `${API_BASE}/api/v1/dashboard/overview${qs}`);
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
  const res = await authedFetch(session, `${API_BASE}/api/v1/review-queue?${qs.toString()}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load review queue"));
  return res.json();
}

export async function fetchAuditLog(
  session: AuthSession,
  options?: { offset?: number; limit?: number; action?: string },
) {
  const qs = new URLSearchParams({
    offset: String(options?.offset ?? 0),
    limit: String(options?.limit ?? 50),
  });
  if (options?.action) qs.set("action", options.action);
  const res = await authedFetch(session, `${API_BASE}/api/v1/audit?${qs.toString()}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load activity log"));
  return res.json();
}

export async function fetchQuestionnaire(session: AuthSession, questionnaireId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires/${questionnaireId}`);
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
  const res = await authedFetch(
    session,
    `${API_BASE}/api/v1/questionnaires/${questionnaireId}/export/${format}?${qs.toString()}`,
  );
  if (!res.ok) throw new Error(await readApiError(res, "Export failed"));
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? `questionnaire.${format}`;
  return { blob, filename };
}

export async function fetchAnswerLibrary(
  session: AuthSession,
  options?: { query?: string; projectId?: string | null; limit?: number },
) {
  const qs = new URLSearchParams({ limit: String(options?.limit ?? 50) });
  if (options?.query) qs.set("query", options.query);
  if (options?.projectId) qs.set("project_id", options.projectId);
  const res = await authedFetch(session, `${API_BASE}/api/v1/answer-library?${qs}`);
  if (!res.ok) throw new Error("Failed to load answer library");
  return res.json();
}

export async function fetchAnswerLibraryEntry(session: AuthSession, entryId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/answer-library/${entryId}`);
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
  const res = await authedFetch(session, `${API_BASE}/api/v1/stale-answers?${qs.toString()}`);
  if (!res.ok) throw new Error("Failed to load stale answers");
  return res.json();
}

export async function fetchStaleAnswerDetail(session: AuthSession, answerId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/stale-answers/${answerId}`);
  if (!res.ok) throw new Error("Failed to load stale answer detail");
  return res.json();
}

export async function revalidateStaleAnswer(session: AuthSession, answerId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/stale-answers/${answerId}/revalidate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Revalidation failed");
  return res.json();
}

export async function regenerateStaleAnswer(session: AuthSession, answerId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/stale-answers/${answerId}/regenerate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Regeneration failed");
  return res.json();
}

export async function validateLibraryEntry(session: AuthSession, entryId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/answer-library/${entryId}/validation`);
  if (!res.ok) throw new Error("Failed to validate library entry");
  return res.json();
}

export async function createSource(
  session: AuthSession,
  payload: {
    name: string;
    source_type: string;
    project_id?: string;
    scope?: string;
    config?: Record<string, unknown>;
  },
) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/sources`, {
    method: "POST",
    body: JSON.stringify({
      scope: "project",
      ...payload,
    }),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to create source"));
  return res.json();
}

export async function triggerSourceSync(session: AuthSession, sourceId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/sources/${sourceId}/sync`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to start sync"));
  return res.json();
}

export async function uploadSourceFiles(session: AuthSession, sourceId: string, files: File[]) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const res = await authedFormFetch(session, `${API_BASE}/api/v1/sources/${sourceId}/files`, form);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to upload files"));
  return res.json();
}

export async function fetchSourceJobs(session: AuthSession, sourceId: string, limit = 5) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/sources/${sourceId}/jobs?limit=${limit}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load sync history"));
  return res.json();
}

export async function fetchSyncJob(session: AuthSession, jobId: string) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/sources/jobs/${jobId}`);
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load sync job"));
  return res.json();
}

export async function connectGithubRepo(
  session: AuthSession,
  payload: {
    source_id: string;
    repository_full_name: string;
    branch?: string;
    access_token?: string;
  },
) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/sources/github/connect-repo`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to connect repository"));
  return res.json();
}

export async function createQuestionnaire(
  session: AuthSession,
  payload: {
    name: string;
    project_id?: string;
    recipient?: string;
    description?: string;
  },
) {
  const res = await authedFetch(session, `${API_BASE}/api/v1/questionnaires`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to create questionnaire"));
  return res.json();
}

export async function uploadQuestionnaireFile(
  session: AuthSession,
  questionnaireId: string,
  file: File,
) {
  const form = new FormData();
  form.append("file", file);
  const res = await authedFormFetch(
    session,
    `${API_BASE}/api/v1/questionnaires/${questionnaireId}/upload`,
    form,
  );
  if (!res.ok) throw new Error(await readApiError(res, "Failed to upload questionnaire"));
  return res.json();
}

export async function regenerateQuestionAnswer(session: AuthSession, questionId: string) {
  const res = await authedFetch(
    session,
    `${API_BASE}/api/v1/questionnaires/questions/${questionId}/regenerate`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(await readApiError(res, "Unable to generate answer. Please try again."));
  return res.json();
}
