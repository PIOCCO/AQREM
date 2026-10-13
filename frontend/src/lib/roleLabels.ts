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

export const PLATFORM_ROLE_LABELS: Record<string, string> = {
  SUPER_ADMIN: "Super admin",
  PLATFORM_SUPPORT: "Support",
  PLATFORM_BILLING: "Billing",
};

export function platformRoleLabel(role: string): string {
  return PLATFORM_ROLE_LABELS[role] ?? role;
}

/** Platform console may only invite organization administrators. */
export const PLATFORM_ORG_INVITE_ROLES = ["ORG_ADMIN"] as const;

export function licenseStatusLabel(status: string): string {
  const map: Record<string, string> = {
    active: "Active",
    suspended: "Suspended",
    test: "Test",
    expired: "Expired",
  };
  return map[status] ?? status;
}
