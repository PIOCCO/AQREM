import type { UserRole } from "./roles";

export const ROLE_LABELS: Record<UserRole, string> = {
  ORG_ADMIN: "Organization admin",
  EDITOR: "Editor",
  REVIEWER: "Reviewer",
  VIEWER: "Viewer",
};

export const ASSIGNABLE_ROLES: UserRole[] = ["ORG_ADMIN", "EDITOR", "REVIEWER", "VIEWER"];

export function roleLabel(role: string): string {
  return ROLE_LABELS[role as UserRole] ?? role;
}

export function roleDisplayLabel(role: UserRole | string | null | undefined): string {
  if (!role) return "Member";
  return roleLabel(role);
}

export function licenseStatusLabel(status: string): string {
  const map: Record<string, string> = {
    active: "Active",
    suspended: "Suspended",
    test: "Test",
    expired: "Expired",
  };
  return map[status] ?? status;
}
