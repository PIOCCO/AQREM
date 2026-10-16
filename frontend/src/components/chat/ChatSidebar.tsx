import { useEffect, useMemo, useRef, useState, type FormEvent, type RefObject } from "react";
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
import { adminBuildMarker } from "../../lib/appBuildInfo";
import { PRODUCT_V1 } from "../../lib/productV1";
import { AnchoredMenu } from "../ui/AnchoredMenu";
import { SidebarMenuProvider, useSidebarMenu } from "./SidebarMenuContext";

const legacyPrimaryNav = [
  { to: "/projects", label: "Projects", Icon: IconFolder },
  { to: "/sources", label: "Sources", Icon: IconDatabase },
  { to: "/evidence", label: "Evidence", Icon: IconFileText },
  { to: "/questionnaires", label: "Questionnaires", Icon: IconClipboard },
  { to: "/review-queue", label: "Review Queue", Icon: IconCheckCircle, badge: true },
  { to: "/answer-library", label: "Answer Library", Icon: IconLibrary },
  { to: "/audit", label: "Activity", Icon: IconActivity },
  { to: "/settings", label: "Settings", Icon: IconSettings },
];

const primaryNav = PRODUCT_V1 ? [] : legacyPrimaryNav;

type Props = {
  activeConversationId?: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onToggleCollapse: () => void;
  onOpenCommandPalette?: () => void;
};

const SIDEBAR_USER_MENU_ID = "sidebar-user";

function AccountMenuItems({
  email,
  showAdminConsole,
  onClose,
  onLogout,
}: {
  email?: string;
  showAdminConsole?: boolean;
  onClose: () => void;
  onLogout: () => void;
}) {
  const { resolved, toggle } = useTheme();
  return (
    <>
      {email ? <p className="px-3 py-2 text-xs text-chat-muted truncate border-b border-chat-border">{email}</p> : null}
      {showAdminConsole ? (
        <p className="px-3 py-2 text-[11px] text-chat-muted border-b border-chat-border font-mono" aria-label="UI build">
          {adminBuildMarker()}
        </p>
      ) : null}
      {!PRODUCT_V1 ? (
        <Link to="/settings" className="chat-menu-item" role="menuitem" onClick={onClose}>
          Settings
        </Link>
      ) : null}
      {showAdminConsole ? <AdminConsoleLink variant="menu" onNavigate={onClose} /> : null}
      <button
        type="button"
        className="chat-menu-item w-full text-left"
        role="menuitem"
        onClick={() => {
          toggle();
          onClose();
        }}
      >
        Theme: {resolved === "dark" ? "Dark" : "Light"}
      </button>
      <button type="button" className="chat-menu-item w-full text-left text-red-600" role="menuitem" onClick={onLogout}>
        Sign out
      </button>
    </>
  );
}

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
  const { openMenuId, setOpenMenuId } = useSidebarMenu();
  const anchorRef = useRef<HTMLButtonElement>(null);
  // Compact rail and expanded footer are both mounted; each needs its own id,
  // otherwise both menus open at once and the hidden one's outside-click
  // handler closes the menu on mousedown before "Sign out" receives its click.
  const menuId = compact ? `${SIDEBAR_USER_MENU_ID}-compact` : SIDEBAR_USER_MENU_ID;
  const open = openMenuId === menuId;
  const close = () => setOpenMenuId(null);
  const toggle = () => setOpenMenuId(open ? null : menuId);

  if (compact) {
    return (
      <div className="border-t border-chat-border p-2 mt-auto shrink-0">
        <Tooltip label={`${name} — account menu`}>
          <button
            ref={anchorRef}
            type="button"
            className="sidebar-rail-btn mx-auto"
            aria-label="Account menu"
            aria-expanded={open}
            aria-haspopup="menu"
            onClick={toggle}
          >
            <span className="ref-user-avatar">{initials}</span>
          </button>
        </Tooltip>
        <AnchoredMenu open={open} onOpenChange={(v) => setOpenMenuId(v ? menuId : null)} anchorRef={anchorRef} className="w-44" minWidth={176}>
          <AccountMenuItems email={email} showAdminConsole={showAdminConsole} onClose={close} onLogout={onLogout} />
        </AnchoredMenu>
      </div>
    );
  }

  return (
    <div className="border-t border-chat-border p-3 mt-auto shrink-0">
      <div className="flex w-full items-center gap-2 rounded-lg p-1">
        <span className="ref-user-avatar">{initials}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-chat-fg">{name}</p>
          {!PRODUCT_V1 ? <p className="truncate text-xs text-chat-muted">{roleLabel}</p> : null}
        </div>
        <button
          ref={anchorRef}
          type="button"
          className="ref-user-menu-btn"
          aria-label="Account menu"
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={toggle}
        >
          <IconChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>
      <AnchoredMenu open={open} onOpenChange={(v) => setOpenMenuId(v ? menuId : null)} anchorRef={anchorRef} className="w-44" minWidth={176}>
        <AccountMenuItems email={email} showAdminConsole={showAdminConsole} onClose={close} onLogout={onLogout} />
      </AnchoredMenu>
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
  scrollRootRef,
}: {
  conversationId: string;
  title: string;
  active?: boolean;
  onRename: (title: string) => void;
  onDelete: (conversationId: string) => void;
  onShare?: () => void;
  scrollRootRef: RefObject<HTMLElement | null>;
}) {
  const menuId = `conv-${conversationId}`;
  const { openMenuId, setOpenMenuId } = useSidebarMenu();
  const open = openMenuId === menuId;
  const anchorRef = useRef<HTMLButtonElement>(null);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [draft, setDraft] = useState(title);

  function submitRename(e: FormEvent) {
    e.preventDefault();
    onRename(draft);
    setEditing(false);
    setOpenMenuId(null);
  }

  return (
    <div className="ref-conv-item-actions">
      <button
        ref={anchorRef}
        type="button"
        className={`chat-conv-menu-btn ref-conv-menu-btn ${active ? "ref-conv-menu-btn-visible" : ""}`}
        aria-label="Conversation actions"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpenMenuId(open ? null : menuId);
        }}
      >
        <IconMore />
      </button>
      <AnchoredMenu
        open={open}
        onOpenChange={(v) => setOpenMenuId(v ? menuId : null)}
        anchorRef={anchorRef}
        scrollRootRef={scrollRootRef}
        align="end"
      >
        <button
          type="button"
          className="chat-menu-item w-full flex items-center gap-2"
          role="menuitem"
          onClick={() => {
            setEditing(true);
            setDraft(title);
            setOpenMenuId(null);
          }}
        >
          <IconEdit /> Rename
        </button>
        {onShare ? (
          <button
            type="button"
            className="chat-menu-item w-full flex items-center gap-2"
            role="menuitem"
            onClick={() => {
              onShare();
              setOpenMenuId(null);
            }}
          >
            Share link
          </button>
        ) : null}
        <button
          type="button"
          className="chat-menu-item w-full flex items-center gap-2 text-[var(--color-danger)]"
          role="menuitem"
          onClick={() => {
            setOpenMenuId(null);
            setConfirmDelete(true);
          }}
        >
          <IconTrash /> Delete
        </button>
      </AnchoredMenu>
      <ConfirmDialog
        open={confirmDelete}
        title="Delete conversation?"
        description={<>This removes “{title}” from your device. This cannot be undone.</>}
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          onDelete(conversationId);
          setConfirmDelete(false);
        }}
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
    if (!session || PRODUCT_V1) return;
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
  const convScrollRef = useRef<HTMLElement>(null);
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
    <SidebarMenuProvider>
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
              window.location.replace("/login");
            }}
            showAdminConsole={showAdminConsole}
          />
        </div>

        <div className="chat-sidebar-expanded-only flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden">
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

            {primaryNav.length > 0 ? (
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
            ) : null}

            {primaryNav.length > 0 ? <div className="mx-3 border-t border-chat-border" /> : null}

            <nav
              ref={convScrollRef}
              className="ref-conv-scroll flex-1 overflow-x-hidden overflow-y-auto px-2 py-3 space-y-4 min-h-0 min-w-0"
              aria-label="Chat history"
            >
              {groups.length === 0 ? (
                <p className="px-2 text-xs text-chat-muted">No conversations yet</p>
              ) : (
                groups.map((group) => (
                  <div key={group.label} className="min-w-0 max-w-full">
                    <p className="px-2 py-1 text-[11px] font-medium text-chat-muted">{group.label}</p>
                    <ul className="min-w-0 max-w-full space-y-0.5">
                      {group.items.map((c) => {
                        const active = c.id === activeConversationId;
                        return (
                          <li
                            key={c.id}
                            className="ref-conv-row group"
                            data-active={active ? "true" : "false"}
                          >
                            <NavLink
                              to={`/c/${c.id}`}
                              onClick={onCloseMobile}
                              className={`ref-conv-item-link ${active ? "ref-conv-item-link-active" : ""}`}
                            >
                              <Tooltip label={c.title}>
                                <span className="ref-conv-item-title">{c.title}</span>
                              </Tooltip>
                            </NavLink>
                            <ConversationMenu
                              conversationId={c.id}
                              title={c.title}
                              active={active}
                              scrollRootRef={convScrollRef}
                              onRename={(t) => rename(c.id, t)}
                              onShare={
                                PRODUCT_V1
                                  ? undefined
                                  : () => {
                                      const url = `${window.location.origin}/c/${c.id}`;
                                      void navigator.clipboard
                                        .writeText(url)
                                        .then(() => toast.push("Conversation link copied"));
                                    }
                              }
                              onDelete={(id) => {
                                const wasActive = activeConversationId === id;
                                remove(id);
                                toast.push("Conversation deleted");
                                if (wasActive) {
                                  navigate("/", { replace: true });
                                  dispatchFocusComposer();
                                }
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
                window.location.replace("/login");
              }}
              showAdminConsole={showAdminConsole}
            />
        </div>
      </aside>
    </SidebarMenuProvider>
  );
}
