/** Resolve API origin: env override, or direct backend port when using Vite on 5173/4173. */

export function resolveApiBase(): string {
  const fromEnv = (import.meta.env.VITE_API_BASE as string | undefined)?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");

  if (typeof window === "undefined") return "";

  const { protocol, hostname, port } = window.location;
  if (port === "5173" || port === "4173") {
    return `${protocol}//${hostname}:8000`;
  }
  return "";
}
