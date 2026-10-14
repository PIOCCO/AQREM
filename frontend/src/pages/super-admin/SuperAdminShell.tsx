import { NavLink, Outlet } from "react-router-dom";
import { LogoHomeLink } from "../../components/brand/LogoHomeLink";

const NAV = [
  { to: "/super-admin/organizations", label: "Organizations" },
  { to: "/super-admin/licenses", label: "Licenses" },
  { to: "/super-admin/deployments", label: "Deployments" },
  { to: "/super-admin/usage", label: "Usage" },
  { to: "/super-admin/audit", label: "Audit" },
  { to: "/super-admin/settings", label: "Settings" },
] as const;

export default function SuperAdminShell() {
  return (
    <div className="admin-shell font-sans text-chat-fg min-h-[100dvh] flex flex-col" data-testid="super-admin-shell">
      <header className="border-b border-chat-border bg-chat-surface px-6 py-4">
        <LogoHomeLink variant="full" className="mb-2" />
        <h1 className="text-xl font-semibold tracking-tight">Super Admin</h1>
        <p className="text-sm text-chat-muted mt-1">
          Platform operations only — no customer questionnaires, evidence, or answer library content.
        </p>
      </header>
      <div className="flex flex-1 min-h-0 flex-col lg:flex-row">
        <nav
          className="lg:w-56 shrink-0 border-b lg:border-b-0 lg:border-r border-chat-border bg-[var(--color-surface)] p-3 flex lg:flex-col gap-1 overflow-x-auto"
          aria-label="Super Admin sections"
        >
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
        </nav>
        <div className="flex-1 min-w-0 overflow-auto">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
