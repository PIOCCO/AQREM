/** Top-level URL segments that are app routes, not pasted invitation tokens. */
const RESERVED_ROOT_SEGMENTS = new Set([
  "login",
  "accept-invite",
  "join",
  "admin",
  "super-admin",
  "platform-admin",
  "master-admin",
  "forgot-password",
  "reset-password",
  "change-password",
  "register",
  "signup",
  "share",
  "chat",
  "dashboard",
  "projects",
  "sources",
  "evidence",
  "questionnaires",
  "review-queue",
  "answer-library",
  "stale-answers",
  "audit",
  "settings",
  "c",
]);

/**
 * Users often paste only the token as the path (/TOKEN) instead of /accept-invite?token=….
 * Detect that pattern so we can route to the invitation flow before role-based redirects.
 */
export function extractRootPastedToken(pathname: string): string | null {
  const trimmed = pathname.replace(/^\/+|\/+$/g, "");
  if (!trimmed || trimmed.includes("/")) return null;
  const lower = trimmed.toLowerCase();
  if (RESERVED_ROOT_SEGMENTS.has(lower)) return null;
  if (trimmed.length < 10) return null;
  return trimmed;
}

export function acceptInviteUrlForToken(token: string): string {
  return `/invite/admin/${encodeURIComponent(token)}`;
}

export function joinUrlForToken(token: string): string {
  return `/join/${encodeURIComponent(token)}`;
}
