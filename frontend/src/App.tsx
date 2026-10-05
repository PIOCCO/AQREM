import { Link, Route, Routes } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import EvidencePage from "./pages/EvidencePage";
import SourcesPage from "./pages/SourcesPage";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/sources", label: "Sources" },
  { to: "/evidence", label: "Evidence" },
];

export default function App() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r border-slate-200 p-6">
        <div className="text-xl font-semibold mb-8">AQREM</div>
        <nav className="space-y-2">
          {nav.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="block rounded-lg px-3 py-2 text-sm hover:bg-slate-100"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-8">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
        </Routes>
      </main>
    </div>
  );
}
