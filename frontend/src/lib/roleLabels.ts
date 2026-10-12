import type { UserRole } from "./roles";

export function roleDisplayLabel(role?: UserRole | string): string {
  switch (role) {
    case "ORG_ADMIN":
      return "Workspace admin";
    case "EDITOR":
      return "Editor";
    case "REVIEWER":
      return "Reviewer";
    case "VIEWER":
      return "Viewer";
    default:
      return "Member";
  }
}
