import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogoHomeLink } from "../brand/LogoHomeLink";
import { useAuth } from "../../lib/authContext";
import { roleDisplayLabel } from "../../lib/roleLabels";
import { clearSession } from "../../lib/api";
import { fetchOrgOverview } from "../../lib/orgAdminApi";
const NAV_FULL = [
  { to: "/org-admin", end: true, label: "Overview" },
  { to: "/org-admin/users", label: "Members" },
  { to: "/org-admin/usage", label: "Usage" },
  { to: "/org-admin/documents", label: "Documents" },
  { to: "/org-admin/access", label: "Access" },
  { to: "/org-admin/data-storage", label: "Settings" },
  { to: "/org-admin/audit", label: "Audit log" },
  { to: "/org-admin/privacy", label: "Privacy" },
];

const NAV = NAV_FULL;

export default function ClientAdminShell() {
  const { user, session } = useAuth();
  const navigate = useNavigate();
  const [incomplete, setIncomplete] = useState<number | null>(null);

  function signOut() {
    clearSession();
    navigate("/login", { replace: true });
  }

  useEffect(() => {
    if (!session) return;
    fetchOrgOverview(session)
      .then((o) => setIncomplete(o.setup.incomplete_count))
      .catch(() => setIncomplete(null));
  }, [session]);

  return (
    <div className="min-h-[100dvh] flex bg-[var(--admin-canvas)] text-[var(--color-text-primary)]">
      <aside className="w-64 shrink-0 border-r border-chat-border bg-chat-surface flex flex-col min-h-screen">
        <div className="p-5 border-b border-chat-border space-y-2">
          <div className="flex items-center justify-between gap-2">
            <LogoHomeLink variant="full" />
            <span className="text-[10px] font-semibold uppercase tracking-wide text-chat-muted border border-chat-border rounded px-1.5 py-0.5">
              Admin
            </span>
          </div>
          <Link to="/" className="text-xs text-[var(--color-link)] hover:underline">
            Back to assistant
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-0.5" aria-label="Client administration">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-chat-surface-subtle font-medium" : "text-chat-muted hover:bg-chat-hover"
                }`
              }
            >
              <span>{item.label}</span>
              {item.end && incomplete != null && incomplete > 0 ? (
                <span
                  className="text-xs rounded-full bg-[var(--chat-brand-mark)] text-white px-2 py-0.5 min-w-[1.25rem] text-center"
                  aria-label={`${incomplete} setup steps incomplete`}
                >
                  {incomplete}
                </span>
              ) : null}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-chat-border space-y-3">
          <Link to="/chat" className="text-xs text-[var(--chat-brand-mark)] hover:underline">
            Open employee assistant ↗
          </Link>
          <div className="flex items-center gap-2 text-xs">
            <span className="w-8 h-8 rounded-full bg-chat-surface-subtle flex items-center justify-center font-medium">
              {(user?.fullName ?? "A").slice(0, 2).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium truncate">{user?.fullName}</p>
              <p className="text-chat-muted">{roleDisplayLabel(user?.role ?? null)}</p>
            </div>
          </div>
          <button
            type="button"
            className="text-xs text-red-600 hover:underline text-left"
            onClick={signOut}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
