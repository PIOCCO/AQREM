export async function readApiError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.message === "string") return body.message;
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return fallback;
  } catch {
    /* ignore */
  }
  if (res.status === 403) return "You do not have permission to perform this action.";
  if (res.status === 401) return "Your session has expired. Please sign in again.";
  if (res.status >= 500) return "Something went wrong. Please try again.";
  return fallback;
}
