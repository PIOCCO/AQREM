import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import RequireAuth from "./components/RequireAuth";
import { ToastProvider } from "./components/ui/Toast";
import { ProjectProvider } from "./lib/projectContext";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import SettingsPage from "./pages/SettingsPage";
import AuditLogPage from "./pages/AuditLogPage";
import DashboardPage from "./pages/DashboardPage";
import EvidenceDetailPage from "./pages/EvidenceDetailPage";
import EvidencePage from "./pages/EvidencePage";
import LoginPage from "./pages/LoginPage";
import AnswerLibraryDetailPage from "./pages/AnswerLibraryDetailPage";
import AnswerLibraryPage from "./pages/AnswerLibraryPage";
import ProjectsPage from "./pages/ProjectsPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import StaleAnswerDetailPage from "./pages/StaleAnswerDetailPage";
import StaleAnswersPage from "./pages/StaleAnswersPage";
import QuestionReviewPage from "./pages/QuestionReviewPage";
import QuestionnaireDetailPage from "./pages/QuestionnaireDetailPage";
import QuestionnairesPage from "./pages/QuestionnairesPage";
import SourcesPage from "./pages/SourcesPage";
import { loadSession } from "./lib/api";

function AuthenticatedApp() {
  return (
    <ToastProvider>
      <ProjectProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="evidence" element={<EvidencePage />} />
            <Route path="evidence/:evidenceId" element={<EvidenceDetailPage />} />
            <Route path="questionnaires" element={<QuestionnairesPage />} />
            <Route path="questionnaires/:questionnaireId" element={<QuestionnaireDetailPage />} />
            <Route
              path="questionnaires/:questionnaireId/questions/:questionId/review"
              element={<QuestionReviewPage />}
            />
            <Route path="review-queue" element={<ReviewQueuePage />} />
            <Route path="answer-library" element={<AnswerLibraryPage />} />
            <Route path="answer-library/:entryId" element={<AnswerLibraryDetailPage />} />
            <Route path="stale-answers" element={<StaleAnswersPage />} />
            <Route path="stale-answers/:answerId" element={<StaleAnswerDetailPage />} />
            <Route path="audit" element={<AuditLogPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ProjectProvider>
    </ToastProvider>
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
            <AuthenticatedApp />
          </RequireAuth>
        }
      />
    </Routes>
  );
}
