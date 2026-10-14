export type CopyResult = { ok: true } | { ok: false; error: string };

/** Copy text; works on http:// LAN hosts where navigator.clipboard is blocked. */
export async function copyToClipboard(text: string): Promise<CopyResult> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return { ok: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Clipboard denied";
      const fallback = execCommandCopy(text);
      if (fallback) return { ok: true };
      return { ok: false, error: msg };
    }
  }
  if (execCommandCopy(text)) return { ok: true };
  return { ok: false, error: "Clipboard unavailable in this browser" };
}

function execCommandCopy(text: string): boolean {
  if (typeof document === "undefined") return false;
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  try {
    return document.execCommand("copy");
  } finally {
    document.body.removeChild(ta);
  }
}
