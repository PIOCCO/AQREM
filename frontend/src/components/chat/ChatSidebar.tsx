import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import {
  IconActivity,
  IconCheckCircle,
  IconChevronDown,
  IconClipboard,
  IconEdit,
  IconFileText,
  IconFolder,
  IconLibrary,
  IconMessage,
  IconMore,
  IconPlus,
  IconSearch,
  IconSettings,
  IconSidebar,
  IconSun,
  IconMoon,
  IconTrash,
} from "../icons/Icons";
import { Logo, LogoMark } from "../ui/Logo";
import { clearSession } from "../../lib/api";
import { useAuth } from "../../lib/authContext";
import { groupConversationsByRecency } from "../../lib/conversations";
import { useConversations } from "../../lib/conversationContext";
import { useProjectContext } from "../../lib/projectContext";
import { useTheme } from "../../lib/themeContext";

const workspaceNav = [
  { to: "/projects", label: "Projects", Icon: IconFolder },
  { to: "/evidence", label: "Evidence", Icon: IconFileText },
  { to: "/questionnaires", label: "Questionnaires", Icon: IconClipboard },
  { to: "/answer-library", label: "Answer library", Icon: IconLibrary },
  { to: "/review-queue", label: "Review queue", Icon: IconCheckCircle },
  { to: "/stale-answers", label: "Stale answers", Icon: IconActivity },
  { to: "/audit", label: "Activity", Icon: IconActivity },
];

type Props = {
  activeConversationId?: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onToggleCollapse: () => void;
};

function UserMenu({
  email,
  name,
  onLogout,
}: {
  email?: string;
  name?: string;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const initial = (name?.trim()?.[0] || email?.[0] || "?").toUpperCase();

  return (
    <div className="relative">
      <button
        type="button"
        className="chat-sidebar-user"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="chat-avatar">{initial}</span>
        <span className="min-w-0 flex-1 truncate text-left text-sm">{name || email || "Account"}</span>
        <IconChevronDown className="h-4 w-4 shrink-0 opacity-60" />
      </button>
      {open ? (
        <>
          <button type="button" className="fixed inset-0 z-40" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 right-0 mb-1 z-50 rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer">
            <p className="px-3 py-2 text-xs text-chat-muted truncate border-b border-chat-border">{email}</p>
            <Link to="/settings" className="chat-menu-item" onClick={() => setOpen(false)}>
              Settings
            </Link>
            <button type="button" className="chat-menu-item w-full text-red-600 dark:text-red-400" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function ConversationMenu({
  conversationId,
  title,
  onRename,
  onDelete,
}: {
  conversationId: string;
  title: string;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  function submitRename(e: FormEvent) {
    e.preventDefault();
    onRename(draft);
    setEditing(false);
    setOpen(false);
  }

  return (
    <div className="relative shrink-0" ref={ref}>
      <button
        type="button"
        className="chat-conv-menu-btn opacity-0 group-hover:opacity-100 focus:opacity-100"
        aria-label="Conversation actions"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        <IconMore />
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer">
          <button
            type="button"
            className="chat-menu-item w-full flex items-center gap-2"
            onClick={() => {
              setEditing(true);
              setDraft(title);
            }}
          >
            <IconEdit /> Rename
          </button>
          <button
            type="button"
            className="chat-menu-item w-full flex items-center gap-2 text-red-600 dark:text-red-400"
            onClick={() => {
              onDelete();
              setOpen(false);
            }}
          >
            <IconTrash /> Delete
          </button>
        </div>
      ) : null}
      {editing ? (
        <form
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4"
          onSubmit={submitRename}
        >
          <div className="w-full max-w-sm rounded-xl border border-chat-border bg-chat-surface p-4 shadow-composer">
            <label className="block text-sm font-medium mb-2">Rename chat</label>
            <input
              className="chat-sidebar-search mb-3"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button type="button" className="chat-ghost-btn" onClick={() => setEditing(false)}>
                Cancel
              </button>
              <button type="submit" className="chat-primary-btn">
                Save
              </button>
            </div>
          </div>
        </form>
      ) : null}
    </div>
  );
}

export default function ChatSidebar({
  activeConversationId,
  collapsed,
  mobileOpen,
  onCloseMobile,
  onToggleCollapse,
}: Props) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { projects, projectId, setProjectId, projectName } = useProjectContext();
  const { conversations, createNew, remove, rename } = useConversations();
  const { toggle, resolved } = useTheme();
  const [search, setSearch] = useState("");
  const [workspaceOpen, setWorkspaceOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, search]);

  const groups = useMemo(() => groupConversationsByRecency(filtered), [filtered]);

  function logout() {
    clearSession();
    navigate("/login", { replace: true });
  }

  function newChat() {
    const conv = createNew(projectId);
    onCloseMobile();
    navigate(`/c/${conv.id}`);
  }

  const asideClass = [
    "chat-sidebar",
    collapsed ? "chat-sidebar-collapsed" : "",
    mobileOpen ? "chat-sidebar-mobile-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      {mobileOpen ? (
        <button type="button" className="chat-sidebar-backdrop lg:hidden" aria-label="Close sidebar" onClick={onCloseMobile} />
      ) : null}
      <aside className={asideClass} aria-label="Sidebar">
        <div className="chat-sidebar-header">
          {!collapsed ? <Logo compact /> : <LogoMark className="h-8 w-8 mx-auto" />}
          <button type="button" className="chat-icon-btn hidden lg:inline-flex" onClick={onToggleCollapse} aria-label="Toggle sidebar">
            <IconSidebar className="h-5 w-5" />
          </button>
        </div>

        {!collapsed ? (
          <>
            <div className="px-2 pb-2 space-y-1">
              <button type="button" className="chat-new-chat-btn" onClick={newChat}>
                <IconPlus className="h-4 w-4" />
                New chat
              </button>
              <div className="relative px-1">
                <IconSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-chat-muted pointer-events-none" />
                <input
                  className="chat-sidebar-search pl-9"
                  placeholder="Search chats"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>

            <nav className="flex-1 overflow-y-auto px-2 pb-2 space-y-3" aria-label="Chat history">
              {groups.length === 0 ? (
                <p className="px-2 text-xs text-chat-muted">No conversations yet</p>
              ) : (
                groups.map((group) => (
                  <div key={group.label}>
                    <p className="px-2 py-1 text-[11px] font-medium text-chat-muted">{group.label}</p>
                    <ul className="space-y-0.5">
                      {group.items.map((c) => {
                        const active = c.id === activeConversationId;
                        return (
                          <li key={c.id} className="group relative flex items-center">
                            <NavLink
                              to={`/c/${c.id}`}
                              onClick={onCloseMobile}
                              className={`chat-conv-link flex-1 ${active ? "chat-conv-link-active" : ""}`}
                            >
                              <IconMessage className="h-4 w-4 shrink-0 opacity-70" />
                              <span className="truncate">{c.title}</span>
                            </NavLink>
                            <ConversationMenu
                              conversationId={c.id}
                              title={c.title}
                              onRename={(t) => rename(c.id, t)}
                              onDelete={() => {
                                remove(c.id);
                                if (activeConversationId === c.id) navigate("/");
                              }}
                            />
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))
              )}
            </nav>

            <div className="border-t border-chat-border px-2 py-2">
              <button
                type="button"
                className="chat-workspace-toggle"
                onClick={() => setWorkspaceOpen((v) => !v)}
                aria-expanded={workspaceOpen}
              >
                Workspace
                <IconChevronDown className={`h-4 w-4 transition-transform ${workspaceOpen ? "rotate-180" : ""}`} />
              </button>
              {workspaceOpen ? (
                <ul className="mt-1 space-y-0.5 pb-2">
                  {workspaceNav.map(({ to, label, Icon }) => (
                    <li key={to}>
                      <NavLink to={to} onClick={onCloseMobile} className={({ isActive }) => `chat-workspace-link ${isActive ? "chat-workspace-link-active" : ""}`}>
                        <Icon className="h-4 w-4 opacity-70" />
                        {label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            <div className="border-t border-chat-border p-2 space-y-2">
              <label className="sr-only" htmlFor="sidebar-project">
                Project scope
              </label>
              <select
                id="sidebar-project"
                className="chat-sidebar-search text-sm"
                value={projectId ?? ""}
                onChange={(e) => setProjectId(e.target.value || null)}
              >
                <option value="">All projects</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {projectName ? <p className="px-1 text-[11px] text-chat-muted truncate">Scope: {projectName}</p> : null}
              <div className="flex items-center gap-1">
                <button type="button" className="chat-icon-btn flex-1" onClick={toggle} aria-label="Toggle theme">
                  {resolved === "dark" ? <IconSun className="h-4 w-4" /> : <IconMoon className="h-4 w-4" />}
                  <span className="text-xs">{resolved === "dark" ? "Light" : "Dark"}</span>
                </button>
                <Link to="/settings" className="chat-icon-btn" aria-label="Settings">
                  <IconSettings className="h-4 w-4" />
                </Link>
              </div>
              <UserMenu email={user?.email} name={user?.fullName} onLogout={logout} />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 py-3">
            <button type="button" className="chat-icon-btn" onClick={newChat} aria-label="New chat">
              <IconPlus className="h-5 w-5" />
            </button>
            <Link to="/projects" className="chat-icon-btn" aria-label="Projects">
              <IconFolder className="h-5 w-5" />
            </Link>
          </div>
        )}
      </aside>
    </>
  );
}
