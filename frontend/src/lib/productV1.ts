/**
 * Version 1 employee surface (default). Legacy UI only when build sets VITE_PRODUCT_V1=false.
 * Also enforced at build time in vite.config.ts `define`.
 */
function readProductV1Flag(): boolean {
  const raw = import.meta.env.VITE_PRODUCT_V1;
  if (raw === undefined || raw === null || String(raw).trim() === "") return true;
  return String(raw).toLowerCase() !== "false";
}

export const PRODUCT_V1 = readProductV1Flag();

/** Workspace routes hidden in V1 (code remains; not linked in UI). */
export const V1_HIDDEN_WORKSPACE_ROUTES = [
  "/dashboard",
  "/projects",
  "/sources",
  "/evidence",
  "/questionnaires",
  "/review-queue",
  "/answer-library",
  "/stale-answers",
  "/audit",
  "/settings",
] as const;

export const V1_EMPLOYEE_NOT_FOUND_MESSAGE =
  "I couldn't find this in the company documents. Please ask your admin.";

export const V1_COMPOSER_DISCLAIMER =
  "AQREM can make mistakes. Check important answers against the source documents.";
