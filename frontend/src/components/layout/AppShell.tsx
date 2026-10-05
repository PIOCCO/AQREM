import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearSession } from "../../lib/api";
import { useAuth } from "../../lib/authContext";
import { useProjectContext } from "../../lib/projectContext";

const navMain = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/projects", label: "Projects" },
];

const navEvidence = [
  { to: "/sources", label: "Sources" },
  { to: "/evidence", label: "Evidence" },
];

const navWorkflow = [
  { to: "/questionnaires", label: "Questionnaires" },
  { to: "/review-queue", label: "Review Queue" },
  { to: "/answer-library", label: "Answer Library" },
];

const navSystem = [
  { to: "/audit", label: "Activity" },
  { to: "/settings", label: "Settings" },
];

function NavGroup({ title, items }: { title: string; items: { to: string; label: string; end?: boolean }[] }) {
  return (
    <div className="mb-4">
      <p className="px-3 mb-1 text-label uppercase tracking-wide text-slate-400">{title}</p>
      <div className="space-y-0.5">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `aq-nav-link ${isActive ? "aq-nav-link-active" : ""}`}
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

export default function AppShell() {
  const { user } = useAuth();
  const { projects, projectId, setProjectId, projectName } = useProjectContext();
  const [navOpen, setNavOpen] = useState(false);
  const navigate = useNavigate();

  function logout() {
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-surface-muted">
      <header className="lg:hidden sticky top-0 z-40 border-b border-border bg-surface px-4 h-14 flex items-center justify-between">
        <button type="button" className="aq-btn-ghost px-2 py-1" onClick={() => setNavOpen((v) => !v)}>
          Menu
        </button>
        <span className="font-semibold text-slate-900">AQREM</span>
        <button type="button" className="aq-btn-ghost px-2 py-1 text-xs" onClick={logout}>
          Sign out
        </button>
      </header>

      <aside
        className={`${navOpen ? "block" : "hidden"} lg:block w-full lg:w-60 xl:w-64 shrink-0 border-b lg:border-b-0 lg:border-r border-border bg-surface lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto`}
      >
        <div className="p-4 lg:p-5 border-b border-border hidden lg:flex items-center justify-between gap-2">
          <span className="text-base font-semibold tracking-tight text-slate-900">AQREM</span>
          {user && (
            <span className="text-[11px] text-slate-500 truncate max-w-[9rem]" title={user.email}>
              {user.email}
            </span>
          )}
        </div>

        <div className="p-4 lg:px-5 lg:pb-5 border-b border-border lg:border-b-0">
          <label className="text-label uppercase tracking-wide text-slate-500">Project</label>
          <select
            className="aq-select mt-1.5"
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
          {projectName && <p className="text-xs text-slate-500 mt-1.5">Scope: {projectName}</p>}
        </div>

        <nav className="p-3 lg:px-4 lg:py-4">
          <NavGroup title="Overview" items={navMain} />
          <NavGroup title="Evidence" items={navEvidence} />
          <NavGroup title="Workflow" items={navWorkflow} />
          <Link to="/stale-answers" className="aq-nav-link text-warning-text mb-4">
            Stale answers
          </Link>
          <NavGroup title="System" items={navSystem} />
        </nav>

        <div className="hidden lg:block p-4 lg:px-5 border-t border-border mt-auto">
          <button type="button" onClick={logout} className="aq-btn-ghost w-full justify-start px-2">
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="hidden lg:flex h-14 shrink-0 items-center border-b border-border bg-surface px-6">
          <p className="text-sm text-slate-600">
            Evidence-backed questionnaire responses
            {projectName ? <span className="text-slate-900 font-medium"> · {projectName}</span> : null}
          </p>
        </header>
        <main className="flex-1 p-4 sm:p-6 lg:p-8 min-w-0">
          <div className="aq-page">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
