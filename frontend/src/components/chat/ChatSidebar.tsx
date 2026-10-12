import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import {
  IconCheckCircle,
  IconClipboard,
  IconDatabase,
  IconEdit,
  IconFileText,
  IconFolder,
  IconLibrary,
  IconMore,
  IconPlus,
  IconSearch,
  IconActivity,
  IconSettings,
  IconSidebar,
  IconSparkles,
  IconTrash,
} from "../icons/Icons";
import { Logo, LogoMark } from "../ui/Logo";
import { clearSession, fetchReviewQueue } from "../../lib/api";
import { useAuth } from "../../lib/authContext";
import { groupConversationsByRecency } from "../../lib/conversations";
import { useConversations } from "../../lib/conversationContext";
import { useProjectContext } from "../../lib/projectContext";
import { roleDisplayLabel } from "../../lib/roleLabels";

const primaryNav = [
  { to: "/projects", label: "Projects", Icon: IconFolder },
  { to: "/projects", label: "Sources", Icon: IconDatabase, match: (p: string) => p.startsWith("/projects") },
  { to: "/evidence", label: "Evidence", Icon: IconFileText },
  { to: "/questionnaires", label: "Questionnaires", Icon: IconClipboard },
  { to: "/review-queue", label: "Review Queue", Icon: IconCheckCircle, badge: true },
  { to: "/answer-library", label: "Answer Library", Icon: IconLibrary },
  { to: "/audit", label: "Activity", Icon: IconActivity },
  { to: "/settings", label: "Settings", Icon: IconSettings },
];

type Props = {
  activeConversationId?: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onToggleCollapse: () => void;
};

function SidebarUserFooter({
  initials,
  name,
  roleLabel,
  email,
  onLogout,
}: {
  initials: string;
  name: string;
  roleLabel: string;
  email?: string;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-chat-border p-3 mt-auto relative">
      <button type="button" className="flex w-full items-center gap-2 rounded-lg hover:bg-chat-hover p-1" onClick={() => setOpen((v) => !v)}>
        <span className="ref-user-avatar">{initials}</span>
        <div className="min-w-0 flex-1 text-left">
          <p className="truncate text-sm font-medium text-chat-fg">{name}</p>
          <p className="truncate text-xs text-chat-muted">{roleLabel}</p>
        </div>
        <Link to="/settings" className="ref-sidebar-sparkle-btn" aria-label="Settings" onClick={(e) => e.stopPropagation()}>
          <IconSparkles className="h-4 w-4" />
        </Link>
      </button>
      {open ? (
        <>
          <button type="button" className="fixed inset-0 z-40" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-3 right-3 mb-1 z-50 rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer">
            {email ? <p className="px-3 py-2 text-xs text-chat-muted truncate border-b border-chat-border">{email}</p> : null}
            <Link to="/settings" className="chat-menu-item" onClick={() => setOpen(false)}>
              Settings
            </Link>
            <button type="button" className="chat-menu-item w-full text-left text-red-600" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function ConversationMenu({
  title,
  onRename,
  onDelete,
}: {
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
          <button type="button" className="chat-menu-item w-full flex items-center gap-2" onClick={() => { setEditing(true); setDraft(title); }}>
            <IconEdit /> Rename
          </button>
          <button type="button" className="chat-menu-item w-full flex items-center gap-2 text-red-600" onClick={() => { onDelete(); setOpen(false); }}>
            <IconTrash /> Delete
          </button>
        </div>
      ) : null}
      {editing ? (
        <form className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4" onSubmit={submitRename}>
          <div className="w-full max-w-sm rounded-xl border border-chat-border bg-chat-surface p-4 shadow-composer">
            <label className="block text-sm font-medium mb-2">Rename chat</label>
            <input className="chat-sidebar-search mb-3" value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
            <div className="flex justify-end gap-2">
              <button type="button" className="chat-ghost-btn" onClick={() => setEditing(false)}>Cancel</button>
              <button type="submit" className="chat-primary-btn">Save</button>
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
  const { user, session } = useAuth();
  const { projectId } = useProjectContext();
  const { conversations, createNew, remove, rename } = useConversations();
  const [search, setSearch] = useState("");
  const [reviewCount, setReviewCount] = useState<number | null>(null);

  useEffect(() => {
    if (!session) return;
    fetchReviewQueue(session, { project_id: projectId ?? undefined, limit: 1, offset: 0 })
      .then((data: { total?: number }) => setReviewCount(typeof data.total === "number" ? data.total : null))
      .catch(() => setReviewCount(null));
  }, [session?.token, session?.organizationId, projectId]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, search]);

  const groups = useMemo(() => groupConversationsByRecency(filtered), [filtered]);

  const initials = useMemo(() => {
    const name = user?.fullName?.trim();
    if (name) {
      const parts = name.split(/\s+/);
      return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
    }
    return (user?.email?.[0] ?? "?").toUpperCase();
  }, [user?.fullName, user?.email]);

  function newChat() {
    const conv = createNew(projectId);
    onCloseMobile();
    navigate(`/c/${conv.id}`);
  }

  const asideClass = ["chat-sidebar", collapsed ? "chat-sidebar-collapsed" : "", mobileOpen ? "chat-sidebar-mobile-open" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      {mobileOpen ? (
        <button type="button" className="chat-sidebar-backdrop lg:hidden" aria-label="Close sidebar" onClick={onCloseMobile} />
      ) : null}
      <aside className={asideClass} aria-label="Sidebar">
        <div className="ref-sidebar-header">
          {!collapsed ? <Logo /> : <LogoMark className="h-8 w-8 mx-auto" />}
          <button type="button" className="ref-sidebar-collapse-btn hidden lg:inline-flex" onClick={onToggleCollapse} aria-label="Toggle sidebar">
            <IconSidebar className="h-[18px] w-[18px]" />
          </button>
        </div>

        {!collapsed ? (
          <>
            <div className="px-3 pb-2 space-y-2">
              <button type="button" className="ref-new-chat-btn" onClick={newChat}>
                <IconPlus className="h-4 w-4" />
                New chat
              </button>
              <div className="relative">
                <IconSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-chat-muted pointer-events-none" />
                <input
                  className="ref-sidebar-search pl-9"
                  placeholder="Search conversations"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>

            <nav className="px-2 pb-3 space-y-0.5" aria-label="Workspace">
              {primaryNav.map(({ to, label, Icon, badge }) => (
                <NavLink
                  key={label}
                  to={to}
                  onClick={onCloseMobile}
                  className={({ isActive }) => `ref-nav-item ${isActive ? "ref-nav-item-active" : ""}`}
                >
                  <Icon className="h-[18px] w-[18px] shrink-0 opacity-80" />
                  <span className="flex-1 truncate">{label}</span>
                  {badge && reviewCount != null && reviewCount > 0 ? (
                    <span className="ref-nav-badge">{reviewCount > 99 ? "99+" : reviewCount}</span>
                  ) : null}
                </NavLink>
              ))}
            </nav>

            <div className="mx-3 border-t border-chat-border" />

            <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-4 min-h-0" aria-label="Chat history">
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
                              className={`ref-conv-item flex-1 ${active ? "ref-conv-item-active" : ""}`}
                            >
                              <span className="truncate">{c.title}</span>
                            </NavLink>
                            <ConversationMenu
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

            <SidebarUserFooter
              initials={initials}
              name={user?.fullName || user?.email || "User"}
              roleLabel={roleDisplayLabel(user?.role)}
              email={user?.email}
              onLogout={() => {
                clearSession();
                navigate("/login", { replace: true });
              }}
            />
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 py-3">
            <button
              type="button"
              className="ref-sidebar-collapse-btn"
              onClick={onToggleCollapse}
              aria-label="Expand sidebar"
              title="Expand sidebar"
            >
              <IconSidebar className="h-[18px] w-[18px]" />
            </button>
            <button type="button" className="chat-icon-btn focus-visible:ref-focus-ring" onClick={newChat} aria-label="New chat">
              <IconPlus className="h-5 w-5" />
            </button>
            <Link to="/settings" className="chat-icon-btn focus-visible:ref-focus-ring" aria-label="Settings">
              <IconSettings className="h-5 w-5" />
            </Link>
          </div>
        )}
      </aside>
    </>
  );
}
