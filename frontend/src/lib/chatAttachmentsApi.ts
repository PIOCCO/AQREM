import { resolveApiBase } from "./apiBase";
import type { AuthSession } from "./api";
import { readApiError } from "./errors";

const UPLOAD_TIMEOUT_MS = 120_000;

export type ChatAttachmentLimits = {
  max_bytes_per_file: number;
  max_files_per_message: number;
  max_total_bytes_per_message: number;
  max_pdf_pages: number;
  max_text_chars: number;
  uploads_per_hour: number;
  allowed_extensions: string[];
  helper_text: string;
};

export type ChatAttachmentUploadResult = {
  id: string;
  file_name: string;
  size_bytes: number;
  status: string;
  index_progress: number;
};

function headers(session: AuthSession): HeadersInit {
  return {
    Authorization: `Bearer ${session.token}`,
    "X-Organization-Id": session.organizationId!,
  };
}

export async function fetchChatAttachmentLimits(): Promise<ChatAttachmentLimits> {
  const res = await fetch(`${resolveApiBase()}/api/v1/chat/attachment-limits`);
  if (!res.ok) throw new Error("Failed to load attachment limits");
  return res.json();
}

export async function uploadChatAttachment(
  session: AuthSession,
  file: File,
  signal?: AbortSignal,
): Promise<ChatAttachmentUploadResult> {
  const form = new FormData();
  form.append("file", file);
  const timeout = AbortSignal.timeout(UPLOAD_TIMEOUT_MS);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  const res = await fetch(`${resolveApiBase()}/api/v1/chat/attachments`, {
    method: "POST",
    headers: headers(session),
    body: form,
    signal: combined,
  });
  if (!res.ok) {
    let message = "Upload failed";
    try {
      const body = await res.json();
      message = body?.detail?.message ?? body?.detail ?? message;
      if (typeof message !== "string") message = readApiErrorFromBody(body) ?? message;
    } catch {
      message = await readApiError(res, message);
    }
    const err = new Error(message) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function readApiErrorFromBody(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const d = (body as { detail?: unknown }).detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object" && "message" in d && typeof (d as { message: unknown }).message === "string") {
    return (d as { message: string }).message;
  }
  return null;
}

export async function fetchChatAttachmentStatus(
  session: AuthSession,
  documentId: string,
): Promise<ChatAttachmentUploadResult & { failure_reason?: string | null }> {
  const res = await fetch(`${resolveApiBase()}/api/v1/chat/attachments/${documentId}`, {
    headers: headers(session),
  });
  if (!res.ok) throw new Error(await readApiError(res, "Failed to load attachment status"));
  return res.json();
}

export async function deleteChatAttachment(session: AuthSession, documentId: string): Promise<void> {
  const res = await fetch(`${resolveApiBase()}/api/v1/chat/attachments/${documentId}`, {
    method: "DELETE",
    headers: headers(session),
  });
  if (!res.ok && res.status !== 204) throw new Error(await readApiError(res, "Failed to remove attachment"));
}
