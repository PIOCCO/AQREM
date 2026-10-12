import { useState } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import ChatSidebar from "../chat/ChatSidebar";
import { ChatMobileMenuButton } from "../../pages/ChatPage";
import CommandPalette from "../ui/CommandPalette";
import { LogoMark } from "../ui/Logo";
import RouteErrorBoundary from "../ui/RouteErrorBoundary";
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts";
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
  const [commandOpen, setCommandOpen] = useState(false);

  const activeConversationId = location.pathname.startsWith("/c/") ? params.conversationId : undefined;

  useKeyboardShortcuts([
    { key: "b", ctrlOrMeta: true, handler: () => setSidebarCollapsed((v) => !v) },
    { key: "k", ctrlOrMeta: true, handler: () => setCommandOpen(true) },
  ]);

  return (
    <div className="h-screen flex overflow-hidden bg-chat-main text-chat-fg font-sans">
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
      <ChatSidebar
        activeConversationId={activeConversationId}
        collapsed={sidebarCollapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
        onOpenCommandPalette={() => setCommandOpen(true)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {!chatMode ? (
          <header className="chat-topbar flex h-[52px] shrink-0 items-center gap-3 px-4 lg:px-6 max-w-[var(--workspace-column-max)] w-full mx-auto">
            <ChatMobileMenuButton onClick={() => setMobileOpen(true)} />
            <LogoMark className="h-8 w-8 lg:hidden" />
            <h1 className="truncate text-sm font-medium">{pageTitleForPath(location.pathname)}</h1>
          </header>
        ) : null}

        <main
          className={`flex-1 min-h-0 min-w-0 overflow-x-hidden ${
            chatMode ? "" : "overflow-y-auto chat-workspace-main"
          }`}
        >
          <RouteErrorBoundary key={location.pathname}>
            <Outlet
              context={{
                openMobileSidebar: () => setMobileOpen(true),
                sidebarCollapsed,
                expandSidebar: () => setSidebarCollapsed(false),
                toggleSidebar: () => setSidebarCollapsed((v) => !v),
                openCommandPalette: () => setCommandOpen(true),
              }}
            />
          </RouteErrorBoundary>
        </main>
      </div>
    </div>
  );
}
