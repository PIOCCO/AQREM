export const ADMIN_CONSOLE_ACCESS = "admin_console:access";

export function hasAdminConsoleAccess(permissions: readonly string[] | null | undefined): boolean {
  return Boolean(permissions?.includes(ADMIN_CONSOLE_ACCESS));
}
