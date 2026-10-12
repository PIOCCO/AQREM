import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

type Command = { id: string; label: string; hint?: string; run: () => void };

type Props = {
  open: boolean;
  onClose: () => void;
  extraCommands?: Command[];
};

const NAV: Omit<Command, "run">[] = [
  { id: "chat", label: "New chat", hint: "Home" },
  { id: "projects", label: "Projects" },
  { id: "evidence", label: "Evidence" },
  { id: "questionnaires", label: "Questionnaires" },
  { id: "review", label: "Review Queue" },
  { id: "library", label: "Answer Library" },
  { id: "activity", label: "Activity" },
  { id: "settings", label: "Settings" },
];

export default function CommandPalette({ open, onClose, extraCommands = [] }: Props) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo<Command[]>(() => {
    const routes: Record<string, () => void> = {
      chat: () => navigate("/"),
      projects: () => navigate("/projects"),
      evidence: () => navigate("/evidence"),
      questionnaires: () => navigate("/questionnaires"),
      review: () => navigate("/review-queue"),
      library: () => navigate("/answer-library"),
      activity: () => navigate("/audit"),
      settings: () => navigate("/settings"),
    };
    const base = NAV.map((c) => ({ ...c, run: () => { routes[c.id](); onClose(); } }));
    return [...extraCommands, ...base];
  }, [extraCommands, navigate, onClose]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(needle) || c.hint?.toLowerCase().includes(needle));
  }, [commands, q]);

  useEffect(() => {
    if (!open) return;
    setQ("");
    inputRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="aq-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="aq-modal max-w-lg"
        role="dialog"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          className="aq-input mb-3"
          placeholder="Search commands…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search commands"
        />
        <ul className="max-h-64 overflow-y-auto space-y-0.5">
          {filtered.length === 0 ? (
            <li className="text-sm text-[var(--color-text-muted)] px-2 py-3">No matching commands</li>
          ) : (
            filtered.map((cmd) => (
              <li key={cmd.id}>
                <button
                  type="button"
                  className="w-full text-left rounded-lg px-3 py-2 text-sm hover:bg-surface-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-focus-ring)]"
                  onClick={cmd.run}
                >
                  <span className="text-[var(--color-text-primary)]">{cmd.label}</span>
                  {cmd.hint ? <span className="text-[var(--color-text-muted)] ml-2 text-xs">{cmd.hint}</span> : null}
                </button>
              </li>
            ))
          )}
        </ul>
        <p className="text-xs text-[var(--color-text-muted)] mt-3">Esc to close · Ctrl+K / ⌘K</p>
      </div>
    </div>
  );
}
