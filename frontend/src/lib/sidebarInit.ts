/** Inline in index.html before paint; keep in sync with SidebarProvider. */
export const SIDEBAR_COLLAPSED_KEY = "aqrem_sidebar_collapsed";

export function readSidebarCollapsedFromStorage(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function applySidebarCollapsed(collapsed: boolean) {
  document.documentElement.dataset.sidebarCollapsed = collapsed ? "true" : "false";
}

export function persistSidebarCollapsed(collapsed: boolean) {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore quota / private mode */
  }
  applySidebarCollapsed(collapsed);
}
