/** Display invitation URLs returned by the API (prefer invitation_setup_url / join_url). */

export function publicAppBaseUrl(): string {
  const fromEnv = (import.meta.env.VITE_PUBLIC_APP_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  return window.location.origin.replace(/\/+$/, "");
}

export function absoluteInviteUrl(pathOrUrl: string | null | undefined): string | null {
  if (!pathOrUrl) return null;
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  const base = publicAppBaseUrl();
  const path = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
  return `${base}${path}`;
}

export function pickInviteUrl(row: {
  invite_url?: string | null;
  invitation_setup_url?: string | null;
  join_url?: string | null;
  invite_path?: string | null;
  invitation_setup_path?: string | null;
  join_path?: string | null;
}): string | null {
  return (
    row.invite_url ??
    row.invitation_setup_url ??
    row.join_url ??
    absoluteInviteUrl(row.invite_path ?? row.invitation_setup_path ?? row.join_path)
  );
}
