import { useMemo, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  IconActivity,
  IconBell,
  IconCheckCircle,
  IconChevronDown,
  IconClipboard,
  IconDashboard,
  IconDatabase,
  IconFileText,
  IconFolder,
  IconLibrary,
  IconSearch,
  IconSettings,
} from "../icons/Icons";
import { Logo, LogoMark } from "../ui/Logo";
import RouteErrorBoundary from "../ui/RouteErrorBoundary";
import { clearSession } from "../../lib/api";
import { useAuth } from "../../lib/authContext";
import { useProjectContext } from "../../lib/projectContext";
import { pageTitleForPath } from "../../lib/routeMeta";

const navItems = [
  { to: "/", label: "Dashboard", end: true, Icon: IconDashboard },
  { to: "/projects", label: "Projects", Icon: IconFolder },
  { to: "/sources", label: "Sources", Icon: IconDatabase },
  { to: "/evidence", label: "Evidence", Icon: IconFileText },
  { to: "/questionnaires", label: "Questionnaires", Icon: IconClipboard },
  { to: "/answer-library", label: "Answer Library", Icon: IconLibrary },
  { to: "/review-queue", label: "Review Queue", Icon: IconCheckCircle },
  { to: "/stale-answers", label: "Stale Answers", Icon: IconActivity },
  { to: "/audit", label: "Audit Log", Icon: IconActivity },
  { to: "/settings", label: "Settings", Icon: IconSettings },
];

function UserAvatar({ name, email, className = "" }: { name?: string; email?: string; className?: string }) {
  const initial = (name?.trim()?.[0] || email?.[0] || "?").toUpperCase();
  return (
    <span
      className={`inline-flex h-9 w-9 shrink-0 flex-none items-center justify-center rounded-full bg-gradient-to-br from-brand-violet/20 to-brand-blue/30 text-sm font-semibold text-slate-700 border border-border ${className}`}
      aria-hidden
    >
      {initial}
    </span>
  );
}

export default function AppShell() {
  const { user } = useAuth();
  const { projects, projectId, setProjectId, projectName } = useProjectContext();
  const [navOpen, setNavOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [headerSearch, setHeaderSearch] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const breadcrumb = pageTitleForPath(location.pathname);

  const workspaceLabel = useMemo(() => {
    if (projectName) return `${projectName} Workspace`;
    return "Organization Workspace";
  }, [projectName]);

  function logout() {
    clearSession();
    navigate("/login", { replace: true });
  }

  function onHeaderSearchSubmit(e: FormEvent) {
    e.preventDefault();
    const q = headerSearch.trim();
    if (q) navigate(`/evidence?search=${encodeURIComponent(q)}`);
    else navigate("/evidence");
  }

  return (
    <div className="min-h-screen flex bg-surface-canvas font-sans">
      <header className="lg:hidden sticky top-0 z-40 border-b border-border bg-surface px-4 h-header flex items-center justify-between">
        <button type="button" className="aq-btn-ghost px-2 py-1" onClick={() => setNavOpen((v) => !v)}>
          Menu
        </button>
        <Logo compact />
        <div className="flex items-center gap-2">
          <select
            className="aq-select max-w-[8rem] text-xs py-1 h-8"
            value={projectId ?? ""}
            onChange={(e) => setProjectId(e.target.value || null)}
            aria-label="Project scope"
          >
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <UserAvatar name={user?.fullName} email={user?.email} />
        </div>
      </header>

      <aside
        className={`${navOpen ? "block" : "hidden"} lg:flex lg:flex-col w-full lg:w-sidebar shrink-0 border-b lg:border-b-0 lg:border-r border-border bg-surface lg:sticky lg:top-0 lg:h-screen`}
      >
        <div className="p-5 border-b border-border hidden lg:block">
          <Logo />
        </div>

        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {navItems.map(({ to, label, end, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) =>
                `ref-nav-link ${isActive ? "ref-nav-link-active" : ""}`
              }
            >
              <Icon className="h-5 w-5 opacity-80" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-border hidden lg:block">
          <div className="ref-workspace-switcher">
            <LogoMark className="h-9 w-9 text-xs" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-900 truncate">{workspaceLabel}</p>
              <label className="sr-only" htmlFor="workspace-project">
                Project scope
              </label>
              <select
                id="workspace-project"
                className="mt-0.5 w-full bg-transparent text-xs text-slate-500 border-0 p-0 focus:ring-0 cursor-pointer truncate"
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
            </div>
            <UserAvatar name={user?.fullName} email={user?.email} />
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="hidden lg:flex h-header shrink-0 items-center gap-6 border-b border-border bg-surface px-6 xl:px-8">
          <p className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900">{breadcrumb}</p>
          <div className="flex shrink-0 items-center gap-4">
            <form onSubmit={onHeaderSearchSubmit} className="relative w-52 xl:w-64">
              <IconSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input
                className="ref-header-search"
                placeholder="Search"
                value={headerSearch}
                onChange={(e) => setHeaderSearch(e.target.value)}
              />
            </form>
            <div className="flex items-center gap-2 border-l border-border pl-4">
              <Link
                to="/audit"
                className="relative inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-control border border-border text-slate-600 hover:bg-surface-subtle transition-colors"
                aria-label="Activity and notifications"
              >
                <IconBell className="h-5 w-5" />
                <span className="absolute top-2.5 right-2.5 h-2 w-2 rounded-full bg-error" aria-hidden />
              </Link>
              <div className="relative">
              <button
                type="button"
                className="ref-header-user-btn"
                onClick={() => setMenuOpen((v) => !v)}
                aria-expanded={menuOpen}
                aria-label="Account menu"
              >
                <UserAvatar name={user?.fullName} email={user?.email} />
                <IconChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
              </button>
              {menuOpen && (
                <>
                  <button type="button" className="fixed inset-0 z-40 cursor-default" aria-label="Close menu" onClick={() => setMenuOpen(false)} />
                  <div className="absolute right-0 top-full mt-1 z-50 w-52 aq-card shadow-panel py-1 text-sm">
                    <p className="px-3 py-2 text-slate-500 truncate border-b border-border">{user?.email}</p>
                    <Link to="/settings" className="aq-dropdown-item" onClick={() => setMenuOpen(false)}>
                      Settings
                    </Link>
                    <button type="button" className="aq-dropdown-item w-full text-error-text" onClick={logout}>
                      Sign out
                    </button>
                  </div>
                </>
              )}
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 p-6 lg:p-8 min-w-0 overflow-x-hidden">
          <RouteErrorBoundary key={location.pathname}>
            <Outlet />
          </RouteErrorBoundary>
        </main>
      </div>
    </div>
  );
}
