export function truncateText(text: string | null | undefined, maxChars: number): string {
  if (!text) return "";
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars)}…`;
}

/** Cap stored/list payload size even when the API returns full file bodies (legacy deploys). */
export const EVIDENCE_LIST_CONTENT_CAP = 2000;

export function capEvidenceListContent(content: unknown, maxChars = EVIDENCE_LIST_CONTENT_CAP): {
  text: string;
  truncated: boolean;
} {
  if (content == null) return { text: "", truncated: false };
  const raw = typeof content === "string" ? content : String(content);
  if (raw.length <= maxChars) return { text: raw, truncated: false };
  return { text: `${raw.slice(0, maxChars)}…`, truncated: true };
}

/** Detail view: avoid `split("\\n")` on entire multi‑MB strings (OOM / white screen). */
export const EVIDENCE_DETAIL_SCAN_MAX_CHARS = 512_000;

export function splitLinesLimited(
  text: string,
  maxLines: number,
  maxScanChars = EVIDENCE_DETAIL_SCAN_MAX_CHARS,
): { lines: string[]; truncated: boolean } {
  const scan = text.length > maxScanChars ? text.slice(0, maxScanChars) : text;
  const charTruncated = text.length > maxScanChars;

  const lines: string[] = [];
  let start = 0;
  while (lines.length < maxLines && start <= scan.length) {
    const nl = scan.indexOf("\n", start);
    if (nl === -1) {
      lines.push(scan.slice(start));
      break;
    }
    lines.push(scan.slice(start, nl));
    start = nl + 1;
  }

  const lineTruncated = start < scan.length || (start === scan.length && text.length > scan.length);
  return { lines, truncated: charTruncated || lineTruncated };
}
