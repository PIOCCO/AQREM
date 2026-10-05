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

export async function fetchQuestionnaireQuestions(session: AuthSession, questionnaireId: string) {
  const res = await fetch(`${API_BASE}/api/v1/questionnaires/${questionnaireId}/questions`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to load questions");
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
  if (!res.ok) throw new Error("Failed to generate answers");
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

export async function validateLibraryEntry(session: AuthSession, entryId: string) {
  const res = await fetch(`${API_BASE}/api/v1/answer-library/${entryId}/validation`, {
    headers: authHeaders(session),
  });
  if (!res.ok) throw new Error("Failed to validate library entry");
  return res.json();
}
