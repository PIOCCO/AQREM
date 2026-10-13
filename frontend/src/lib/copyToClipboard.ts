/** Copy text with Clipboard API and a textarea fallback for restricted contexts. */
export async function copyToClipboard(text: string): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return { ok: true };
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Clipboard unavailable";
    const fallback = tryExecCommandCopy(text);
    if (fallback) return { ok: true };
    return { ok: false, error: msg };
  }
  const fallback = tryExecCommandCopy(text);
  if (fallback) return { ok: true };
  return { ok: false, error: "Clipboard is not available in this browser" };
}

function tryExecCommandCopy(text: string): boolean {
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
  } catch {
    return false;
  } finally {
    document.body.removeChild(ta);
  }
}
