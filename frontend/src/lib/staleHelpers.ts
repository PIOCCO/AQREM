export function formatStaleStatus(potentiallyStale: boolean): string {
  return potentiallyStale ? "Potentially Stale" : "Current";
}

export function canReviewerRevalidate(role: string): boolean {
  return role !== "VIEWER";
}

export function shouldShowStaleWarning(potentiallyStale: boolean, changedCount: number): boolean {
  return potentiallyStale || changedCount > 0;
}

export function regenerationSourceLabel(source?: string): string {
  if (source === "stale_regeneration") return "Regenerated (evidence changed)";
  return source?.replaceAll("_", " ") ?? "unknown";
}
