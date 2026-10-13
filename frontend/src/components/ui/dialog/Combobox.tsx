import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type ComboboxOption = {
  value: string;
  label: string;
  meta?: string;
};

type Props = {
  id: string;
  label?: string;
  value: string;
  onChange: (value: string) => void;
  options: ComboboxOption[];
  placeholder?: string;
  disabled?: boolean;
  error?: string | null;
  emptyState?: React.ReactNode;
  "data-testid"?: string;
};

export function Combobox({
  id,
  value,
  onChange,
  options,
  placeholder = "Select…",
  disabled,
  error,
  emptyState,
  "data-testid": testId = "aq-combobox",
}: Props) {
  const listboxId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);

  const selected = options.find((o) => o.value === value);
  const showSearch = options.length > 6;
  const filtered = showSearch
    ? options.filter((o) => o.label.toLowerCase().includes(query.trim().toLowerCase()))
    : options;

  useEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      if (triggerRef.current?.contains(t) || panelRef.current?.contains(t)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const panel =
    open && pos
      ? createPortal(
          <div
            ref={panelRef}
            className="aq-combobox-popover"
            style={{ top: pos.top, left: pos.left, width: pos.width }}
            role="listbox"
            id={listboxId}
            data-testid={`${testId}-popover`}
          >
            {showSearch ? (
              <div className="p-2 border-b border-[var(--color-border)]">
                <input
                  type="search"
                  className="aq-input text-sm"
                  placeholder="Search projects…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  aria-label="Search projects"
                  data-testid={`${testId}-search`}
                />
              </div>
            ) : null}
            {options.length === 0 && emptyState ? (
              <div className="p-3">{emptyState}</div>
            ) : filtered.length === 0 ? (
              <p className="p-3 text-sm text-[var(--color-text-muted)]">No matches</p>
            ) : (
              <ul className="max-h-56 overflow-y-auto py-1">
                {filtered.map((opt) => {
                  const active = opt.value === value;
                  return (
                    <li key={opt.value}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={active}
                        className={`aq-combobox-option ${active ? "aq-combobox-option-active" : ""}`}
                        onClick={() => {
                          onChange(opt.value);
                          setOpen(false);
                          setQuery("");
                          triggerRef.current?.focus();
                        }}
                      >
                        <span className="truncate font-medium">{opt.label}</span>
                        {opt.meta ? <span className="text-xs text-[var(--color-text-muted)] shrink-0">{opt.meta}</span> : null}
                        {active ? <span className="text-[var(--color-accent)] shrink-0" aria-hidden>✓</span> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        className={`aq-combobox-trigger ${error ? "aq-input-error" : ""}`}
        onClick={() => setOpen((v) => !v)}
        data-testid={testId}
      >
        <span className={selected ? "" : "text-[var(--color-text-muted)]"}>{selected?.label ?? placeholder}</span>
        <span className="aq-combobox-chevron" aria-hidden />
      </button>
      {panel}
    </>
  );
}
