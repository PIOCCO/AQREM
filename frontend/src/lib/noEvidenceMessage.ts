export function formatNoEvidenceMessage(projectName: string | null | undefined, sourcesSearched: number): string {
  const label = projectName?.trim() || "this project";
  const n = Math.max(0, sourcesSearched);
  const sourcePhrase = `${n} source${n === 1 ? "" : "s"} searched`;
  return (
    `I couldn't find evidence for that in **${label}** (${sourcePhrase}). ` +
    "Try rephrasing, or add the document that covers it."
  );
}
