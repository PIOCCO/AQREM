import type { ChatAttachmentLimits } from "./chatAttachmentsApi";

export function fileExtension(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".tar.gz")) return ".tar.gz";
  const i = lower.lastIndexOf(".");
  return i >= 0 ? lower.slice(i) : "";
}

export function validateChatFileClient(
  file: File,
  limits: ChatAttachmentLimits,
  existing: File[],
): string | null {
  const ext = fileExtension(file.name);
  if (ext === ".tar.gz" || ext === ".zip") {
    return "Archive files cannot be attached in chat. Use the Documents page for .tar.gz uploads.";
  }
  if (!limits.allowed_extensions.includes(ext)) {
    return `Unsupported type (${ext || "unknown"}). Allowed in chat: ${limits.allowed_extensions.join(", ")}.`;
  }
  if (!file.size) return "This file is empty.";
  if (file.size > limits.max_bytes_per_file) {
    const mb = Math.round(limits.max_bytes_per_file / (1024 * 1024));
    return `This file is too large. The chat limit is ${mb} MB per file.`;
  }
  const dup = existing.some((f) => f.name === file.name && f.size === file.size);
  if (dup) return "This file is already attached to this message.";
  const total = existing.reduce((s, f) => s + f.size, 0) + file.size;
  if (total > limits.max_total_bytes_per_message) {
    const mb = Math.round(limits.max_total_bytes_per_message / (1024 * 1024));
    return `Attachments exceed ${mb} MB total for one message. Remove a file or use Documents.`;
  }
  if (existing.length >= limits.max_files_per_message) {
    return `You can attach up to ${limits.max_files_per_message} files per message.`;
  }
  return null;
}
