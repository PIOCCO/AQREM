import { Link, Navigate, Route, Routes } from "react-router-dom";
import RequireAuth from "./components/RequireAuth";
import DashboardPage from "./pages/DashboardPage";
import EvidencePage from "./pages/EvidencePage";
import LoginPage from "./pages/LoginPage";
import AnswerLibraryDetailPage from "./pages/AnswerLibraryDetailPage";
import AnswerLibraryPage from "./pages/AnswerLibraryPage";
import StaleAnswerDetailPage from "./pages/StaleAnswerDetailPage";
import StaleAnswersPage from "./pages/StaleAnswersPage";
import QuestionReviewPage from "./pages/QuestionReviewPage";
import QuestionnaireDetailPage from "./pages/QuestionnaireDetailPage";
import QuestionnairesPage from "./pages/QuestionnairesPage";
import SourcesPage from "./pages/SourcesPage";
import { loadSession } from "./lib/api";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/sources", label: "Sources" },
  { to: "/evidence", label: "Evidence" },
  { to: "/questionnaires", label: "Questionnaires" },
  { to: "/answer-library", label: "Answer Library" },
  { to: "/stale-answers", label: "Stale Answers" },
];

function AppShell() {
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
          <Route path="/questionnaires" element={<QuestionnairesPage />} />
          <Route path="/questionnaires/:questionnaireId" element={<QuestionnaireDetailPage />} />
          <Route
            path="/questionnaires/:questionnaireId/questions/:questionId/review"
            element={<QuestionReviewPage />}
          />
          <Route path="/answer-library" element={<AnswerLibraryPage />} />
          <Route path="/answer-library/:entryId" element={<AnswerLibraryDetailPage />} />
          <Route path="/stale-answers" element={<StaleAnswersPage />} />
          <Route path="/stale-answers/:answerId" element={<StaleAnswerDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const session = loadSession();
  return (
    <Routes>
      <Route path="/login" element={session ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      />
    </Routes>
  );
}
