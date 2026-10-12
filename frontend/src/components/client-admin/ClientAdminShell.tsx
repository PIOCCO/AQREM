import { NavLink, Outlet, Link } from "react-router-dom";
import { useAuth } from "../../lib/authContext";
import { roleDisplayLabel } from "../../lib/roleLabels";

const NAV = [
  { to: "/admin", end: true, label: "Setup" },
  { to: "/admin/documents", label: "Documents" },
  { to: "/admin/users", label: "Users & access" },
  { to: "/sources", label: "Sources" },
  { to: "/audit", label: "Security & audit" },
  { to: "/settings", label: "Settings" },
];

export default function ClientAdminShell() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen flex bg-[var(--admin-canvas,#f5f5f4)] text-chat-fg">
      <aside className="w-64 shrink-0 border-r border-chat-border bg-chat-surface flex flex-col">
        <div className="p-5 border-b border-chat-border">
          <p className="font-semibold text-sm">{user?.fullName ? "Your organization" : "Admin console"}</p>
          <p className="text-xs text-chat-muted mt-0.5">Admin console</p>
        </div>
        <nav className="flex-1 p-3 space-y-0.5" aria-label="Client administration">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm ${isActive ? "bg-chat-surface-subtle font-medium" : "text-chat-muted hover:bg-chat-hover"}`
              }
            >
              {item.label}
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
            <div>
              <p className="font-medium">{user?.fullName}</p>
              <p className="text-chat-muted">{roleDisplayLabel(user?.role ?? null)}</p>
            </div>
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
