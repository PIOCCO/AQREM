import { useState } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import ChatSidebar from "../chat/ChatSidebar";
import { ChatMobileMenuButton } from "../../pages/ChatPage";
import { LogoMark } from "../ui/Logo";
import RouteErrorBoundary from "../ui/RouteErrorBoundary";
import { pageTitleForPath } from "../../lib/routeMeta";

function isChatRoute(pathname: string) {
  return pathname === "/" || pathname.startsWith("/c/");
}

export default function AppShell() {
  const location = useLocation();
  const params = useParams();
  const chatMode = isChatRoute(location.pathname);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeConversationId = location.pathname.startsWith("/c/") ? params.conversationId : undefined;

  return (
    <div className="h-screen flex overflow-hidden bg-chat-main text-chat-fg font-sans">
      <ChatSidebar
        activeConversationId={activeConversationId}
        collapsed={sidebarCollapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {!chatMode ? (
          <header className="chat-topbar flex h-12 shrink-0 items-center gap-3 px-4 lg:px-6">
            <ChatMobileMenuButton onClick={() => setMobileOpen(true)} />
            <LogoMark className="h-8 w-8 lg:hidden" />
            <h1 className="truncate text-sm font-medium">{pageTitleForPath(location.pathname)}</h1>
          </header>
        ) : (
          <div className="lg:hidden chat-topbar flex h-12 shrink-0 items-center px-3">
            <ChatMobileMenuButton onClick={() => setMobileOpen(true)} />
            <span className="ml-2 text-sm font-medium truncate">AQREM</span>
          </div>
        )}

        <main
          className={`flex-1 min-h-0 min-w-0 overflow-x-hidden ${
            chatMode ? "" : "overflow-y-auto chat-workspace-main"
          }`}
        >
          <RouteErrorBoundary key={location.pathname}>
            <Outlet />
          </RouteErrorBoundary>
        </main>
      </div>
    </div>
  );
}
