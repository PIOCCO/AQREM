/** Display invitation URLs returned by the API (prefer invitation_setup_url / join_url). */

let warnedMissingPublicUrl = false;

export function publicAppBaseUrl(): string {
  const fromEnv = (import.meta.env.VITE_PUBLIC_APP_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  if (typeof window !== "undefined" && !warnedMissingPublicUrl) {
    console.warn(
      "VITE_PUBLIC_APP_URL is not set; falling back to window.location.origin for invite link display. Set VITE_PUBLIC_APP_URL to match PUBLIC_BASE_URL on the API.",
    );
    warnedMissingPublicUrl = true;
  }
  return typeof window !== "undefined" ? window.location.origin.replace(/\/+$/, "") : "";
}

export function absoluteInviteUrl(pathOrUrl: string | null | undefined): string | null {
  if (!pathOrUrl) return null;
  const trimmed = pathOrUrl.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  const base = publicAppBaseUrl();
  if (!base) return null;
  const path = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return `${base}${path}`;
}

/** Last-resort safeguard: never show a bare relative path in the UI. */
export function displayInviteUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  return absoluteInviteUrl(value);
}

export function pickInviteUrl(row: {
  invite_url?: string | null;
  invitation_setup_url?: string | null;
  join_url?: string | null;
  invite_path?: string | null;
  invitation_setup_path?: string | null;
  join_path?: string | null;
}): string | null {
  const raw =
    row.invite_url ??
    row.invitation_setup_url ??
    row.join_url ??
    row.invite_path ??
    row.invitation_setup_path ??
    row.join_path;
  return displayInviteUrl(raw);
}
