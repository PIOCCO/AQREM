import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate } from "react-router-dom";
import { IconCheckCircle, IconChevronDown } from "../icons/Icons";

export type ScopeProject = {
  id: string;
  name: string;
  sourcesCount?: number;
};

type Props = {
  projects: ScopeProject[];
  projectId: string | null;
  onSelectProject: (id: string | null) => void;
  sourcesCount?: number | null;
  disabled?: boolean;
};

const POPOVER_MIN_W = 320;

export default function ScopePicker({ projects, projectId, onSelectProject, sourcesCount, disabled }: Props) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [placement, setPlacement] = useState<"above" | "below">("above");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const triggerLabelId = useId();

  const selectedName = useMemo(() => {
    if (!projectId) return "All projects";
    return projects.find((p) => p.id === projectId)?.name ?? "Project";
  }, [projectId, projects]);

  const options = useMemo(() => {
    const all = [{ id: null as string | null, name: "All projects", sourcesCount: undefined as number | undefined }];
    for (const p of projects) all.push({ id: p.id, name: p.name, sourcesCount: p.sourcesCount });
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter((o) => o.name.toLowerCase().includes(q));
  }, [projects, query]);

  const showSearch = projects.length > 6;

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    triggerRef.current?.focus();
  }, []);

  const updatePlacement = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const spaceAbove = rect.top;
    const spaceBelow = window.innerHeight - rect.bottom;
    setPlacement(spaceAbove >= 280 || spaceAbove > spaceBelow ? "above" : "below");
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePlacement();
    function onResize() {
      updatePlacement();
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [open, updatePlacement]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      if (popoverRef.current?.contains(t) || triggerRef.current?.contains(t)) return;
      close();
    }
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);

  function selectOption(id: string | null) {
    onSelectProject(id);
    close();
  }

  function onTriggerKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpen(true);
      setActiveIndex(0);
    }
  }

  function onListKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Home") {
      e.preventDefault();
      setActiveIndex(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActiveIndex(options.length - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = options[activeIndex];
      if (opt) selectOption(opt.id);
    }
  }

  const popoverStyle = useMemo(() => {
    const el = triggerRef.current;
    if (!el) return {};
    const rect = el.getBoundingClientRect();
    const width = Math.max(POPOVER_MIN_W, rect.width);
    const left = Math.min(rect.left, window.innerWidth - width - 8);
    if (placement === "above") {
      return {
        position: "fixed" as const,
        left,
        width,
        bottom: window.innerHeight - rect.top + 8,
        zIndex: 200,
      };
    }
    return {
      position: "fixed" as const,
      left,
      width,
      top: rect.bottom + 8,
      zIndex: 200,
    };
  }, [open, placement, projectId, projects.length]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        id={triggerLabelId}
        className="scope-picker-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        disabled={disabled}
        onClick={() => {
          setOpen((v) => !v);
          setActiveIndex(0);
        }}
        onKeyDown={onTriggerKeyDown}
      >
        <span className="text-chat-muted text-xs shrink-0">Scope:</span>
        <span className="truncate font-medium text-sm text-chat-fg max-w-[10rem]">{selectedName}</span>
        {projectId && sourcesCount != null ? (
          <span className="text-[11px] text-chat-muted shrink-0">{sourcesCount} src</span>
        ) : null}
        <IconChevronDown className={`h-4 w-4 shrink-0 text-chat-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open
        ? createPortal(
            <div
              ref={popoverRef}
              className={`scope-picker-popover ${placement === "above" ? "scope-picker-popover-above" : "scope-picker-popover-below"}`}
              style={popoverStyle}
              role="presentation"
              onKeyDown={onListKeyDown}
            >
              {showSearch ? (
                <input
                  className="scope-picker-search"
                  placeholder="Search projects…"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActiveIndex(0);
                  }}
                  aria-label="Search projects"
                  autoFocus
                />
              ) : null}

              {projects.length === 0 ? (
                <div className="scope-picker-empty">
                  <p className="text-sm text-chat-fg font-medium">No projects yet</p>
                  <p className="text-xs text-chat-muted mt-1">Create a project to connect sources and search evidence.</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button type="button" className="aq-btn-primary text-sm h-9" onClick={() => navigate("/projects")}>
                      Create project
                    </button>
                    <Link to="/projects" className="aq-btn-secondary text-sm h-9" onClick={close}>
                      Add a source
                    </Link>
                  </div>
                </div>
              ) : (
                <ul id={listboxId} role="listbox" aria-labelledby={triggerLabelId} className="scope-picker-list">
                  {options.map((opt, idx) => {
                    const selected = opt.id === projectId || (opt.id === null && !projectId);
                    return (
                      <li key={opt.id ?? "all"} role="presentation">
                        <button
                          type="button"
                          role="option"
                          aria-selected={selected}
                          className={`scope-picker-option ${idx === activeIndex ? "scope-picker-option-active" : ""}`}
                          onMouseEnter={() => setActiveIndex(idx)}
                          onClick={() => selectOption(opt.id)}
                        >
                          <span className="flex-1 min-w-0 text-left truncate">{opt.name}</span>
                          {opt.sourcesCount != null ? (
                            <span className="text-[11px] text-chat-muted shrink-0">{opt.sourcesCount} sources</span>
                          ) : null}
                          {selected ? <IconCheckCircle className="h-4 w-4 shrink-0 text-[var(--color-accent)]" aria-hidden /> : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              {projects.length > 0 ? (
                <div className="scope-picker-footer">
                  <Link to="/projects" className="text-xs text-link hover:underline" onClick={close}>
                    Manage projects
                  </Link>
                  <button type="button" className="text-xs text-link hover:underline" onClick={() => navigate("/projects")}>
                    New project
                  </button>
                </div>
              ) : null}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
