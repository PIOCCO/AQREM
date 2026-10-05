import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearSession } from "../../lib/api";
import { useProjectContext } from "../../lib/projectContext";

const nav = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/projects", label: "Projects" },
  { to: "/sources", label: "Sources" },
  { to: "/evidence", label: "Evidence" },
  { to: "/questionnaires", label: "Questionnaires" },
  { to: "/review-queue", label: "Review Queue" },
  { to: "/answer-library", label: "Answer Library" },
  { to: "/audit", label: "Activity" },
];

export default function AppShell() {
  const { projects, projectId, setProjectId, projectName } = useProjectContext();
  const [navOpen, setNavOpen] = useState(false);
  const navigate = useNavigate();

  function logout() {
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col lg:flex-row">
      <header className="lg:hidden border-b border-slate-200 bg-white px-4 py-3 flex items-center justify-between">
        <button type="button" className="text-sm font-medium" onClick={() => setNavOpen((v) => !v)}>
          Menu
        </button>
        <span className="font-semibold">AQREM</span>
        <button type="button" className="text-sm text-slate-600" onClick={logout}>
          Sign out
        </button>
      </header>

      <aside
        className={`${navOpen ? "block" : "hidden"} lg:block w-full lg:w-64 shrink-0 bg-white border-b lg:border-b-0 lg:border-r border-slate-200 p-4 lg:p-6`}
      >
        <div className="text-xl font-semibold mb-6 hidden lg:block">AQREM</div>
        <div className="mb-6 space-y-2">
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">Project</label>
          <select
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
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
          {projectName && <p className="text-xs text-slate-500">Filtering: {projectName}</p>}
        </div>
        <nav className="space-y-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"
                }`
              }
              onClick={() => setNavOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
          <Link
            to="/stale-answers"
            className="block rounded-lg px-3 py-2 text-sm text-amber-900 hover:bg-amber-50"
          >
            Stale answers
          </Link>
        </nav>
        <button
          type="button"
          onClick={logout}
          className="mt-8 hidden lg:block text-sm text-slate-600 hover:text-slate-900"
        >
          Sign out
        </button>
      </aside>

      <main className="flex-1 p-4 sm:p-6 lg:p-8 min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
