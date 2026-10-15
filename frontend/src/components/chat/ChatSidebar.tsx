import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import {
  IconCheckCircle,
  IconChevronDown,
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
  IconTrash,
} from "../icons/Icons";
import { commandPaletteShortcutLabel } from "../../lib/keyboardHints";
import { useTheme } from "../../lib/themeContext";
import { LogoHomeLink } from "../brand/LogoHomeLink";
import { dispatchFocusComposer } from "../../lib/chatHome";
import { clearSession, fetchReviewQueue } from "../../lib/api";
import { useToast } from "../ui/Toast";
import { useAuth } from "../../lib/authContext";
import { groupConversationsByRecency } from "../../lib/conversations";
import { useConversations } from "../../lib/conversationContext";
import { useProjectContext } from "../../lib/projectContext";
import { roleDisplayLabel } from "../../lib/roleLabels";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { Tooltip } from "../ui/Tooltip";
import { AdminConsoleLink } from "../nav/AdminConsoleLink";
import { hasAdminConsoleAccess } from "../../lib/permissions";

const primaryNav = [
  { to: "/projects", label: "Projects", Icon: IconFolder },
  { to: "/sources", label: "Sources", Icon: IconDatabase },
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
  onOpenCommandPalette?: () => void;
};

function SidebarUserFooter({
  initials,
  name,
  roleLabel,
  email,
  onLogout,
  compact,
  showAdminConsole,
}: {
  initials: string;
  name: string;
  roleLabel: string;
  email?: string;
  onLogout: () => void;
  compact?: boolean;
  showAdminConsole?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { resolved, toggle } = useTheme();

  if (compact) {
    return (
      <div className="border-t border-chat-border p-2 mt-auto relative shrink-0">
        <Tooltip label={`${name} — account menu`}>
          <button
            type="button"
            className="sidebar-rail-btn mx-auto"
            aria-label="Account menu"
            aria-expanded={open}
            aria-haspopup="menu"
            onClick={() => setOpen((v) => !v)}
          >
            <span className="ref-user-avatar">{initials}</span>
          </button>
        </Tooltip>
        {open ? (
          <>
            <button type="button" className="fixed inset-0 z-40" aria-label="Close menu" onClick={() => setOpen(false)} />
            <div className="absolute bottom-full left-1/2 z-50 mb-2 w-44 -translate-x-1/2 rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer">
              {email ? <p className="px-3 py-2 text-xs text-chat-muted truncate border-b border-chat-border">{email}</p> : null}
              <Link to="/settings" className="chat-menu-item" onClick={() => setOpen(false)}>
                Settings
              </Link>
              {showAdminConsole ? <AdminConsoleLink variant="menu" onNavigate={() => setOpen(false)} /> : null}
              <button type="button" className="chat-menu-item w-full text-left" onClick={() => { toggle(); setOpen(false); }}>
                Theme: {resolved === "dark" ? "Dark" : "Light"}
              </button>
              <button type="button" className="chat-menu-item w-full text-left text-red-600" onClick={onLogout}>
                Sign out
              </button>
            </div>
          </>
        ) : null}
      </div>
    );
  }

  return (
    <div className="border-t border-chat-border p-3 mt-auto relative shrink-0">
      <div className="flex w-full items-center gap-2 rounded-lg p-1">
        <span className="ref-user-avatar">{initials}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-chat-fg">{name}</p>
          <p className="truncate text-xs text-chat-muted">{roleLabel}</p>
        </div>
        <button
          type="button"
          className="ref-user-menu-btn"
          aria-label="Account menu"
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={() => setOpen((v) => !v)}
        >
          <IconChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>
      {open ? (
        <>
          <button type="button" className="fixed inset-0 z-40" aria-label="Close menu" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-3 right-3 mb-1 z-50 rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer">
            {email ? <p className="px-3 py-2 text-xs text-chat-muted truncate border-b border-chat-border">{email}</p> : null}
            <Link to="/settings" className="chat-menu-item" onClick={() => setOpen(false)}>
              Settings
            </Link>
            {showAdminConsole ? <AdminConsoleLink variant="menu" onNavigate={() => setOpen(false)} /> : null}
            <button type="button" className="chat-menu-item w-full text-left" onClick={() => { toggle(); setOpen(false); }}>
              Theme: {resolved === "dark" ? "Dark" : "Light"}
            </button>
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
  conversationId,
  title,
  active,
  onRename,
  onDelete,
  onShare,
}: {
  conversationId: string;
  title: string;
  active?: boolean;
  onRename: (title: string) => void;
  onDelete: (conversationId: string) => void;
  onShare: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
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
    <div className="absolute right-1 top-1/2 z-10 -translate-y-1/2 shrink-0" ref={ref}>
      <button
        type="button"
        className={`chat-conv-menu-btn static translate-y-0 focus-visible:opacity-100 group-focus-within:opacity-100 ${
          active ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
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
          <button type="button" className="chat-menu-item w-full flex items-center gap-2" onClick={() => { onShare(); setOpen(false); }}>
            Share link
          </button>
          <button
            type="button"
            className="chat-menu-item w-full flex items-center gap-2 text-[var(--color-danger)]"
            onClick={() => {
              setOpen(false);
              setConfirmDelete(true);
            }}
          >
            <IconTrash /> Delete
          </button>
        </div>
      ) : null}
      <ConfirmDialog
        open={confirmDelete}
        title="Delete conversation?"
        description={<>This removes “{title}” from your device. This cannot be undone.</>}
        confirmLabel="Delete"
        destructive
        onConfirm={() => onDelete(conversationId)}
        onCancel={() => setConfirmDelete(false)}
      />
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
  onOpenCommandPalette,
}: Props) {
  const navigate = useNavigate();
  const { user, session, loading: authLoading } = useAuth();
  const showAdminConsole = !authLoading && hasAdminConsoleAccess(user?.permissions);
  const { projectId } = useProjectContext();
  const { conversations, remove, rename } = useConversations();
  const toast = useToast();
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
    onCloseMobile();
    navigate("/");
    dispatchFocusComposer();
  }

  const asideClass = ["chat-sidebar", collapsed ? "chat-sidebar-collapsed" : "", mobileOpen ? "chat-sidebar-mobile-open" : ""]
    .filter(Boolean)
    .join(" ");
  const asideRef = useRef<HTMLElement>(null);
  const cmdHint = commandPaletteShortcutLabel();
  const toggleLabel = collapsed ? "Expand sidebar" : "Collapse sidebar";

  useEffect(() => {
    if (!mobileOpen || !asideRef.current) return;
    const focusable = asideRef.current.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    focusable?.focus();
  }, [mobileOpen]);

  return (
    <>
      {mobileOpen ? (
        <button type="button" className="chat-sidebar-backdrop lg:hidden" aria-label="Close sidebar" onClick={onCloseMobile} />
      ) : null}
      <aside ref={asideRef} className={asideClass} aria-label="Sidebar" data-testid="chat-sidebar">
        <div className="ref-sidebar-header">
          <div className={`min-w-0 flex-1 ${collapsed ? "flex justify-center" : ""}`}>
            <LogoHomeLink variant={collapsed ? "mark" : "full"} onNavigate={onCloseMobile} />
          </div>
          <button
            type="button"
            className="ref-sidebar-collapse-btn hidden lg:inline-flex"
            data-testid="sidebar-toggle"
            onClick={onToggleCollapse}
            aria-expanded={!collapsed}
            aria-label={toggleLabel}
          >
            <IconSidebar className="h-[18px] w-[18px]" />
          </button>
        </div>

        <div className="chat-sidebar-collapsed-only flex min-h-0 flex-1 flex-col w-full">
          <nav className="sidebar-rail-nav" aria-label="Workspace (icons)">
            <Tooltip label="New chat">
              <button type="button" className="sidebar-rail-btn" onClick={newChat} aria-label="New chat">
                <IconPlus className="h-5 w-5" />
              </button>
            </Tooltip>
            <Tooltip label={`Search (${cmdHint})`}>
              <button
                type="button"
                className="sidebar-rail-btn"
                aria-label="Search conversations"
                onClick={() => onOpenCommandPalette?.()}
              >
                <IconSearch className="h-5 w-5" />
              </button>
            </Tooltip>
            {primaryNav.map(({ to, label, Icon, badge }, index) => (
              <span key={label} className="contents">
                {index === primaryNav.length - 1 && showAdminConsole ? (
                  <AdminConsoleLink variant="rail" onNavigate={onCloseMobile} />
                ) : null}
                <Tooltip label={label}>
                  <NavLink
                    to={to}
                    onClick={onCloseMobile}
                    className={({ isActive }) => `sidebar-rail-btn ${isActive ? "sidebar-rail-btn-active" : ""}`}
                    aria-label={label}
                  >
                    <Icon className="h-5 w-5" />
                    {badge && reviewCount != null && reviewCount > 0 ? (
                      <span className="sr-only">{reviewCount} in review queue</span>
                    ) : null}
                  </NavLink>
                </Tooltip>
              </span>
            ))}
          </nav>
          <SidebarUserFooter
            compact
            initials={initials}
            name={user?.fullName || user?.email || "User"}
            roleLabel={roleDisplayLabel(user?.role)}
            email={user?.email}
            onLogout={() => {
              clearSession();
              navigate("/login", { replace: true });
            }}
            showAdminConsole={showAdminConsole}
          />
        </div>

        <div className="chat-sidebar-expanded-only flex min-h-0 flex-1 flex-col">
            <div className="px-3 pb-2 space-y-2 shrink-0">
              <button type="button" className="ref-new-chat-btn" onClick={newChat}>
                <IconPlus className="h-4 w-4" />
                New chat
              </button>
              <div className="flex gap-2">
                <div className="ref-sidebar-search-wrap">
                  <IconSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-chat-muted pointer-events-none" />
                  <input
                    className="ref-sidebar-search pl-9 pr-14"
                    placeholder="Search conversations"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    aria-label="Search conversations"
                  />
                  <span className="ref-sidebar-search-kbd" aria-hidden>
                    {cmdHint}
                  </span>
                </div>
              </div>
            </div>

            <nav className="px-2 pb-3 space-y-0.5" aria-label="Workspace">
              {primaryNav.map(({ to, label, Icon, badge }, index) => (
                <span key={label} className="contents">
                  {index === primaryNav.length - 1 && showAdminConsole ? (
                    <AdminConsoleLink variant="sidebar" onNavigate={onCloseMobile} />
                  ) : null}
                  <NavLink
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
                </span>
              ))}
            </nav>

            <div className="mx-3 border-t border-chat-border" />

            <nav className="ref-conv-scroll flex-1 overflow-y-auto px-2 py-3 space-y-4 min-h-0" aria-label="Chat history">
              {groups.length === 0 ? (
                <p className="px-2 text-xs text-chat-muted">No conversations yet</p>
              ) : (
                groups.map((group) => (
                  <div key={group.label}>
                    <p className="px-2 py-1 text-[11px] font-medium text-chat-muted">{group.label}</p>
                    <ul className="min-w-0 space-y-0.5">
                      {group.items.map((c) => {
                        const active = c.id === activeConversationId;
                        return (
                          <li key={c.id} className="group relative min-w-0">
                            <NavLink
                              to={`/c/${c.id}`}
                              onClick={onCloseMobile}
                              title={c.title}
                              className={`ref-conv-item ${active ? "ref-conv-item-active" : ""}`}
                            >
                              <span className="min-w-0 truncate">{c.title}</span>
                            </NavLink>
                            <ConversationMenu
                              conversationId={c.id}
                              title={c.title}
                              active={active}
                              onRename={(t) => rename(c.id, t)}
                              onShare={() => {
                                const url = `${window.location.origin}/c/${c.id}`;
                                void navigator.clipboard.writeText(url).then(() => toast.push("Conversation link copied"));
                              }}
                              onDelete={(id) => {
                                const wasActive = activeConversationId === id;
                                remove(id);
                                toast.push("Conversation deleted");
                                if (wasActive) navigate("/", { replace: true });
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
              showAdminConsole={showAdminConsole}
            />
        </div>
      </aside>
    </>
  );
}
