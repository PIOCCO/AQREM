import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import RequireAuth from "./components/RequireAuth";
import { ToastProvider } from "./components/ui/Toast";
import { ConversationProvider } from "./lib/conversationContext";
import { ProjectProvider } from "./lib/projectContext";
import { ThemeProvider } from "./lib/themeContext";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import SettingsPage from "./pages/SettingsPage";
import AuditLogPage from "./pages/AuditLogPage";
import ChatPage from "./pages/ChatPage";
import DashboardPage from "./pages/DashboardPage";
import EvidenceDetailPage from "./pages/EvidenceDetailPage";
import EvidencePage from "./pages/EvidencePage";
import AcceptInvitePage from "./pages/AcceptInvitePage";
import PlatformAdminPage from "./pages/PlatformAdminPage";
import RequirePlatformAdmin from "./components/RequirePlatformAdmin";
import RequireOrgAdmin from "./components/RequireOrgAdmin";
import ClientAdminShell from "./components/client-admin/ClientAdminShell";
import ClientAdminSetupPage from "./pages/ClientAdminSetupPage";
import ClientAdminUsersPage from "./pages/ClientAdminUsersPage";
import ClientAdminDocumentsPage from "./pages/ClientAdminDocumentsPage";
import ClientAdminModelTokenPage from "./pages/ClientAdminModelTokenPage";
import ClientAdminUsagePage from "./pages/ClientAdminUsagePage";
import ClientAdminAuditPage from "./pages/ClientAdminAuditPage";
import ClientAdminPrivacyPage from "./pages/ClientAdminPrivacyPage";
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
import LoginEntryRedirect from "./components/LoginEntryRedirect";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import RouteErrorBoundary from "./components/ui/RouteErrorBoundary";

function AuthenticatedApp() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ProjectProvider>
          <ConversationProvider>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<ChatPage />} />
                <Route path="chat" element={<ChatPage />} />
                <Route path="c/:conversationId" element={<ChatPage />} />
                <Route path="dashboard" element={<DashboardPage />} />
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
          </ConversationProvider>
        </ProjectProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginEntryRedirect />} />
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />
      <Route path="/platform-admin" element={<Navigate to="/master-admin" replace />} />
      <Route
        path="/master-admin"
        element={
          <RequirePlatformAdmin>
            <RouteErrorBoundary>
              <PlatformAdminPage />
            </RouteErrorBoundary>
          </RequirePlatformAdmin>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAuth>
            <RequireOrgAdmin>
              <ClientAdminShell />
            </RequireOrgAdmin>
          </RequireAuth>
        }
      >
        <Route index element={<ClientAdminSetupPage />} />
        <Route path="documents" element={<ClientAdminDocumentsPage />} />
        <Route path="model-token" element={<ClientAdminModelTokenPage />} />
        <Route path="users" element={<ClientAdminUsersPage />} />
        <Route path="usage" element={<ClientAdminUsagePage />} />
        <Route path="audit" element={<ClientAdminAuditPage />} />
        <Route path="privacy" element={<ClientAdminPrivacyPage />} />
      </Route>
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
