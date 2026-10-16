import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogoHomeLink } from "../../components/brand/LogoHomeLink";
import { clearSession, fetchAuthMePlatform, loadSession } from "../../lib/api";

const NAV = [
  { to: "/super-admin/organizations", label: "Organizations" },
  { to: "/super-admin/licenses", label: "Licenses" },
  { to: "/super-admin/deployments", label: "Deployments" },
  { to: "/super-admin/fleet", label: "Fleet" },
  { to: "/super-admin/usage", label: "Usage" },
  { to: "/super-admin/audit", label: "Audit" },
  { to: "/super-admin/settings", label: "Settings" },
] as const;

export default function SuperAdminShell() {
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState<string | null>(null);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token) return;
    fetchAuthMePlatform(session)
      .then((me) => setDisplayName((me.full_name as string) || (me.email as string) || null))
      .catch(() => setDisplayName(null));
  }, []);

  function signOut() {
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <div className="admin-shell font-sans text-chat-fg min-h-[100dvh] flex flex-col" data-testid="super-admin-shell">
      <header className="border-b border-chat-border bg-chat-surface px-6 py-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <LogoHomeLink variant="full" className="mb-2" />
          <h1 className="text-xl font-semibold tracking-tight">Super Admin</h1>
          <p className="text-sm text-chat-muted mt-1">
            Platform operations only — no customer questionnaires, evidence, or answer library content.
          </p>
        </div>
        <button
          type="button"
          className="lg:hidden shrink-0 text-sm text-red-600 hover:underline"
          onClick={signOut}
        >
          Sign out
        </button>
      </header>
      <div className="flex flex-1 min-h-0 flex-col lg:flex-row">
        <nav
          className="lg:w-56 shrink-0 border-b lg:border-b-0 lg:border-r border-chat-border bg-[var(--color-surface)] p-3 flex lg:flex-col lg:self-stretch gap-1 overflow-x-auto lg:overflow-y-auto"
          aria-label="Super Admin sections"
        >
          <div className="flex lg:flex-col gap-1 min-w-0">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm whitespace-nowrap ${
                    isActive ? "bg-chat-surface-subtle font-medium text-[var(--color-text-primary)]" : "text-chat-muted hover:bg-chat-hover"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          <div className="hidden lg:flex lg:flex-col lg:mt-auto lg:pt-4 lg:border-t lg:border-chat-border lg:gap-2">
            {displayName ? (
              <p className="px-3 text-xs text-chat-muted truncate" title={displayName}>
                {displayName}
              </p>
            ) : null}
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm text-left text-red-600 hover:bg-chat-hover whitespace-nowrap"
              onClick={signOut}
            >
              Sign out
            </button>
          </div>
        </nav>
        <div className="flex-1 min-w-0 overflow-auto">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
