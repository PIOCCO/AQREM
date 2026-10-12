/** Inline in index.html before paint; keep logic in sync with ThemeProvider defaults. */
export const THEME_STORAGE_KEY = "aqrem_theme";

export type StoredTheme = "light" | "dark" | "system";

export function resolveThemeFromStorage(stored: string | null): "light" | "dark" {
  if (stored === "light") return "light";
  if (stored === "dark") return "dark";
  if (stored === "system") {
    return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return "dark";
}

export function applyResolvedTheme(resolved: "light" | "dark") {
  document.documentElement.classList.toggle("dark", resolved === "dark");
  document.documentElement.dataset.theme = resolved;
}
