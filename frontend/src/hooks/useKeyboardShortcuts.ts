import { useEffect } from "react";

type Shortcut = {
  key: string;
  ctrlOrMeta?: boolean;
  shift?: boolean;
  handler: () => void;
};

export function useKeyboardShortcuts(shortcuts: Shortcut[], enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || target?.isContentEditable) {
        if (!(e.key === "k" && (e.metaKey || e.ctrlKey))) return;
      }
      for (const s of shortcuts) {
        if (s.ctrlOrMeta && !(e.metaKey || e.ctrlKey)) continue;
        if (s.shift && !e.shiftKey) continue;
        if (!s.shift && e.shiftKey && s.key.length > 1) continue;
        if (e.key.toLowerCase() !== s.key.toLowerCase()) continue;
        e.preventDefault();
        s.handler();
        return;
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [shortcuts, enabled]);
}
