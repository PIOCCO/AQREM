import { type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import RequireAuth from "./components/RequireAuth";
import { ToastProvider } from "./components/ui/Toast";
import { ConversationProvider } from "./lib/conversationContext";
import { SidebarProvider } from "./lib/sidebarContext";
import { ProjectProvider } from "./lib/projectContext";
import { ThemeProvider } from "./lib/themeContext";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import SettingsPage from "./pages/SettingsPage";
import AuditLogPage from "./pages/AuditLogPage";
import ChatPage from "./pages/ChatPage";
import ShareConversationPage from "./pages/ShareConversationPage";
import DashboardPage from "./pages/DashboardPage";
import EvidenceDetailPage from "./pages/EvidenceDetailPage";
import EvidencePage from "./pages/EvidencePage";
import AcceptInvitePage from "./pages/AcceptInvitePage";
import JoinOrgPage from "./pages/JoinOrgPage";
import SuperAdminShell from "./pages/super-admin/SuperAdminShell";
import SuperAdminOrganizationsPage from "./pages/super-admin/SuperAdminOrganizationsPage";
import SuperAdminLicensesPage from "./pages/super-admin/SuperAdminLicensesPage";
import SuperAdminDeploymentsPage from "./pages/super-admin/SuperAdminDeploymentsPage";
import SuperAdminUsagePage from "./pages/super-admin/SuperAdminUsagePage";
import SuperAdminAuditPage from "./pages/super-admin/SuperAdminAuditPage";
import SuperAdminSettingsPage from "./pages/super-admin/SuperAdminSettingsPage";
import RequireSuperAdmin from "./components/RequireSuperAdmin";
import RequireOrgAdminOnly from "./components/RequireOrgAdminOnly";
import WorkspaceOrInvitationGate from "./components/WorkspaceOrInvitationGate";
import RequireTenantWorkspace from "./components/RequireTenantWorkspace";
import ClientAdminShell from "./components/client-admin/ClientAdminShell";
import ClientAdminSetupPage from "./pages/ClientAdminSetupPage";
import ClientAdminDataStoragePage from "./pages/ClientAdminDataStoragePage";
import ClientAdminUsersPage from "./pages/ClientAdminUsersPage";
import ClientAdminAccessPage from "./pages/ClientAdminAccessPage";
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
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import RouteErrorBoundary from "./components/ui/RouteErrorBoundary";

function PublicTheme({ children }: { children: ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

/** Legacy `/admin` URLs → `/org-admin` (preserve subpath). */
function AdminLegacyRedirect() {
  const { pathname, search, hash } = useLocation();
  const target = pathname.replace(/^\/admin(?=\/|$)/, "/org-admin") + search + hash;
  return <Navigate to={target} replace />;
}

const orgAdminRouteTree = (
  <>
    <Route index element={<ClientAdminSetupPage />} />
    <Route path="documents" element={<ClientAdminDocumentsPage />} />
    <Route path="access" element={<ClientAdminAccessPage />} />
    <Route path="data-storage" element={<ClientAdminDataStoragePage />} />
    <Route path="model-token" element={<ClientAdminModelTokenPage />} />
    <Route path="users" element={<ClientAdminUsersPage />} />
    <Route path="usage" element={<ClientAdminUsagePage />} />
    <Route path="audit" element={<ClientAdminAuditPage />} />
    <Route path="privacy" element={<ClientAdminPrivacyPage />} />
  </>
);

function OrgAdminRouteShell() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <RequireTenantWorkspace>
          <RequireOrgAdminOnly>
            <ClientAdminShell />
          </RequireOrgAdminOnly>
        </RequireTenantWorkspace>
      </ToastProvider>
    </ThemeProvider>
  );
}

function AuthenticatedApp() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ProjectProvider>
          <SidebarProvider>
            <ConversationProvider>
              <Routes>
                <Route element={<AppShell />}>
                <Route index element={<ChatPage />} />
                <Route path="chat" element={<ChatPage />} />
                <Route path="c/:conversationId" element={<ChatPage />} />
                <Route path="share/:shareToken" element={<ShareConversationPage />} />
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
          </SidebarProvider>
        </ProjectProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicTheme>
            <LoginEntryRedirect />
          </PublicTheme>
        }
      />
      <Route
        path="/share/:shareToken"
        element={
          <PublicTheme>
            <ShareConversationPage />
          </PublicTheme>
        }
      />
      <Route
        path="/forgot-password"
        element={
          <PublicTheme>
            <ForgotPasswordPage />
          </PublicTheme>
        }
      />
      <Route
        path="/reset-password"
        element={
          <PublicTheme>
            <ResetPasswordPage />
          </PublicTheme>
        }
      />
      <Route path="/register" element={<Navigate to="/login" replace />} />
      <Route path="/signup" element={<Navigate to="/login" replace />} />
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />
      <Route
        path="/accept-invite"
        element={
          <PublicTheme>
            <AcceptInvitePage />
          </PublicTheme>
        }
      />
      <Route
        path="/invite/admin/:token"
        element={
          <PublicTheme>
            <AcceptInvitePage />
          </PublicTheme>
        }
      />
      <Route
        path="/invite/member/:token"
        element={
          <PublicTheme>
            <AcceptInvitePage />
          </PublicTheme>
        }
      />
      <Route
        path="/join"
        element={
          <PublicTheme>
            <JoinOrgPage />
          </PublicTheme>
        }
      />
      <Route
        path="/join/:token"
        element={
          <PublicTheme>
            <JoinOrgPage />
          </PublicTheme>
        }
      />
      <Route path="/platform-admin" element={<Navigate to="/super-admin" replace />} />
      <Route path="/master-admin" element={<Navigate to="/super-admin" replace />} />
      <Route
        path="/super-admin"
        element={
          <PublicTheme>
            <RequireSuperAdmin>
              <RouteErrorBoundary>
                <SuperAdminShell />
              </RouteErrorBoundary>
            </RequireSuperAdmin>
          </PublicTheme>
        }
      >
        <Route index element={<Navigate to="organizations" replace />} />
        <Route path="organizations" element={<SuperAdminOrganizationsPage />} />
        <Route path="licenses" element={<SuperAdminLicensesPage />} />
        <Route path="deployments" element={<SuperAdminDeploymentsPage />} />
        <Route path="usage" element={<SuperAdminUsagePage />} />
        <Route path="audit" element={<SuperAdminAuditPage />} />
        <Route path="settings" element={<SuperAdminSettingsPage />} />
      </Route>
      <Route path="/org-admin" element={<OrgAdminRouteShell />}>
        {orgAdminRouteTree}
      </Route>
      <Route path="/admin/*" element={<AdminLegacyRedirect />} />
      <Route
        path="/*"
        element={
          <WorkspaceOrInvitationGate>
            <AuthenticatedApp />
          </WorkspaceOrInvitationGate>
        }
      />
    </Routes>
  );
}
