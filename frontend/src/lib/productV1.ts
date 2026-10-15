/**
 * Version 1 product surface: org-wide private assistant + admin documents/members.
 * Set VITE_PRODUCT_V1=false to restore the full navigation and routes (legacy).
 */
export const PRODUCT_V1 = import.meta.env.VITE_PRODUCT_V1 !== "false";

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
