export type UserRole = "ORG_ADMIN" | "EDITOR" | "REVIEWER" | "VIEWER";

const rank: Record<UserRole, number> = {
  VIEWER: 0,
  REVIEWER: 1,
  EDITOR: 2,
  ORG_ADMIN: 3,
};

export function roleAtLeast(role: UserRole, required: UserRole): boolean {
  return rank[role] >= rank[required];
}

export function canEditContent(role: UserRole): boolean {
  return roleAtLeast(role, "EDITOR");
}

export function canReviewAnswers(role: UserRole): boolean {
  return roleAtLeast(role, "REVIEWER");
}

export function canManageOrg(role: UserRole): boolean {
  return roleAtLeast(role, "ORG_ADMIN");
}
