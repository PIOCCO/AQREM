type ValidationIssue = { loc?: unknown[]; msg?: string };

function formatValidationErrors(detail: unknown[]): string | null {
  const parts: string[] = [];
  for (const item of detail) {
    if (!item || typeof item !== "object") continue;
    const issue = item as ValidationIssue;
    const loc = Array.isArray(issue.loc)
      ? issue.loc.filter((x) => x !== "body").map(String).join(".")
      : "";
    const msg = typeof issue.msg === "string" ? issue.msg : "";
    if (msg) parts.push(loc ? `${loc}: ${msg}` : msg);
  }
  return parts.length ? parts.join("; ") : null;
}

export async function readResponseJson(res: Response): Promise<unknown | null> {
  try {
    const text = await res.text();
    if (!text.trim()) return null;
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export type ParsedApiError = { message: string; code?: string };

export function parseApiError(body: unknown, fallback: string, status: number): ParsedApiError {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    const detail = record.detail;
    let code: string | undefined;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const structured = detail as Record<string, unknown>;
      if (typeof structured.code === "string") code = structured.code;
      if (typeof structured.message === "string" && structured.message.trim()) {
        return { message: structured.message, code };
      }
    }
    if (typeof record.message === "string" && record.message.trim()) {
      return { message: record.message, code };
    }
    if (typeof detail === "string") return { message: detail, code };
    if (Array.isArray(detail)) {
      const formatted = formatValidationErrors(detail);
      if (formatted) return { message: formatted, code };
    }
  }
  if (status === 403) return { message: "You do not have permission to perform this action." };
  if (status === 401) return { message: "Your session has expired. Please sign in again." };
  if (status >= 500) return { message: fallback || "Something went wrong. Please try again." };
  return { message: fallback };
}

export function apiErrorMessage(body: unknown, fallback: string, status: number): string {
  return parseApiError(body, fallback, status).message;
}

export async function readApiError(res: Response, fallback: string): Promise<string> {
  const body = await readResponseJson(res);
  return apiErrorMessage(body, fallback, res.status);
}

export async function readApiErrorDetail(res: Response, fallback: string): Promise<ParsedApiError> {
  const body = await readResponseJson(res);
  return parseApiError(body, fallback, res.status);
}
