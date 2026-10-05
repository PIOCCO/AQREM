const titles: Record<string, string> = {
  "/": "Dashboard",
  "/projects": "Projects",
  "/sources": "Sources",
  "/evidence": "Evidence",
  "/questionnaires": "Questionnaires",
  "/review-queue": "Review Queue",
  "/answer-library": "Answer Library",
  "/stale-answers": "Stale Answers",
  "/audit": "Audit Log",
  "/settings": "Settings",
};

export function pageTitleForPath(pathname: string): string {
  if (titles[pathname]) return titles[pathname];
  if (pathname.startsWith("/projects/")) return "Project";
  if (pathname.startsWith("/questionnaires/") && pathname.includes("/review")) return "Question Review";
  if (pathname.startsWith("/questionnaires/")) return "Questionnaire";
  if (pathname.startsWith("/evidence/")) return "Evidence";
  if (pathname.startsWith("/answer-library/")) return "Answer Library";
  if (pathname.startsWith("/stale-answers/")) return "Stale Review";
  return "AQREM";
}
