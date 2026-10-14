import { resolveApiBase } from "./apiBase";

function apiUrl(path: string): string {
  return `${resolveApiBase()}${path}`;
}

export async function previewJoin(token: string): Promise<{ organization_name: string }> {
  const res = await fetch(apiUrl("/api/v1/public/join/preview"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) throw new Error("invalid");
  return res.json();
}

export async function startJoin(payload: { token: string; email: string; full_name: string }) {
  const res = await fetch(apiUrl("/api/v1/public/join/start"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = (body as { detail?: { message?: string } }).detail?.message;
    throw new Error(msg ?? "Could not start join");
  }
  return res.json() as Promise<{
    pending_id: string;
    dev_verification_code?: string | null;
  }>;
}

export async function verifyJoinEmail(payload: { token: string; pending_id: string; code: string }) {
  const res = await fetch(apiUrl("/api/v1/public/join/verify-email"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("invalid_code");
  return res.json();
}

export async function completeJoin(payload: { token: string; pending_id: string; password: string }) {
  const res = await fetch(apiUrl("/api/v1/public/join/complete"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = (body as { detail?: { message?: string } }).detail?.message;
    throw new Error(msg ?? "Could not complete join");
  }
  return res.json() as Promise<{ status: string; access_token?: string; organization_id?: string }>;
}

export type AcceptInvitationPreview = {
  organization_name: string;
  role: string;
  email: string;
  invitee_full_name: string | null;
  status?: "pending" | "expired" | "revoked" | "accepted";
};

export async function previewAcceptInvitation(token: string): Promise<AcceptInvitationPreview> {
  const res = await fetch(apiUrl("/api/v1/auth/accept-invitation/preview"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = (body as { detail?: { message?: string } }).detail?.message;
    throw new Error(msg ?? "invalid");
  }
  return res.json();
}
