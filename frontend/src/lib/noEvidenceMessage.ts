export function formatNoEvidenceMessage(projectName: string | null | undefined, sourcesSearched: number): string {
  const scopedToProject = Boolean(projectName?.trim());
  const label = scopedToProject ? projectName!.trim() : "your organization";
  const n = Math.max(0, sourcesSearched);
  const sourcePhrase = `${n} source${n === 1 ? "" : "s"} searched`;
  const tail = scopedToProject
    ? "Try rephrasing, or add the document that covers it."
    : "Try rephrasing, or ask your admin to add the document that covers it.";
  return `I couldn't find evidence for that in **${label}** (${sourcePhrase}). ${tail}`;
}
