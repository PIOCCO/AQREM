import { useEffect, useState } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import ChatSidebar from "../chat/ChatSidebar";
import { ChatMobileMenuButton } from "../../pages/ChatPage";
import CommandPalette from "../ui/CommandPalette";
import { Logo } from "../brand/Logo";
import RouteErrorBoundary from "../ui/RouteErrorBoundary";
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts";
import { pageTitleForPath } from "../../lib/routeMeta";
import { useSidebar } from "../../lib/sidebarContext";

function isChatRoute(pathname: string) {
  return pathname === "/" || pathname.startsWith("/c/");
}

export default function AppShell() {
  const location = useLocation();
  const params = useParams();
  const chatMode = isChatRoute(location.pathname);
  const { collapsed, mobileOpen, setMobileOpen, toggleCollapsed, expand } = useSidebar();
  const [commandOpen, setCommandOpen] = useState(false);

  const activeConversationId = location.pathname.startsWith("/c/") ? params.conversationId : undefined;

  useKeyboardShortcuts([
    { key: "b", ctrlOrMeta: true, handler: () => toggleCollapsed() },
    { key: "k", ctrlOrMeta: true, handler: () => setCommandOpen(true) },
  ]);

  useEffect(() => {
    if (!mobileOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMobileOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen, setMobileOpen]);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, setMobileOpen]);

  return (
    <div
      className="app-shell"
      data-sidebar-collapsed={collapsed ? "true" : "false"}
      data-testid="app-shell"
    >
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
      <ChatSidebar
        activeConversationId={activeConversationId}
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggleCollapse={toggleCollapsed}
        onOpenCommandPalette={() => setCommandOpen(true)}
      />

      <div className="app-main flex min-w-0 min-h-0 flex-col overflow-hidden">
        {!chatMode ? (
          <header className="chat-topbar flex h-14 shrink-0 items-center gap-3 px-4 lg:px-6 max-w-[var(--workspace-column-max)] w-full mx-auto">
            <ChatMobileMenuButton onClick={() => setMobileOpen(true)} />
            <Logo variant="mark" size={28} className="lg:hidden" />
            {pageTitleForPath(location.pathname) ? (
              <h1 className="truncate text-sm font-medium">{pageTitleForPath(location.pathname)}</h1>
            ) : null}
          </header>
        ) : null}

        <main
          className={`app-main-body flex-1 min-h-0 min-w-0 overflow-hidden ${
            chatMode ? "" : "overflow-y-auto chat-workspace-main"
          }`}
        >
          {/* Chat routes ("/", "/chat", "/c/:id") share one key so the first send's
              "/" -> "/c/:id" URL change doesn't remount ChatPage and abort the reply. */}
          <RouteErrorBoundary
            key={/^\/(chat|c\/[^/]+)?\/?$/.test(location.pathname) ? "chat" : location.pathname}
          >
            <Outlet
              context={{
                openMobileSidebar: () => setMobileOpen(true),
                sidebarCollapsed: collapsed,
                expandSidebar: expand,
                toggleSidebar: toggleCollapsed,
                openCommandPalette: () => setCommandOpen(true),
              }}
            />
          </RouteErrorBoundary>
        </main>
      </div>
    </div>
  );
}
