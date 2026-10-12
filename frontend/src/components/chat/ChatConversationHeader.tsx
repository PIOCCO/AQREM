import { useState } from "react";
import { Link } from "react-router-dom";
import { IconMore, IconShare, IconSidebar } from "../icons/Icons";
import { IconButton } from "../ui/IconButton";
import { useToast } from "../ui/Toast";

type Props = {
  conversationTitle: string;
  onOpenSidebar?: () => void;
  onExpandSidebar?: () => void;
};

export default function ChatConversationHeader({ conversationTitle, onOpenSidebar, onExpandSidebar }: Props) {
  const toast = useToast();
  const [menuOpen, setMenuOpen] = useState(false);

  function shareLink() {
    void navigator.clipboard.writeText(window.location.href);
    toast.push("Link copied to clipboard");
  }

  return (
    <header className="ref-chat-header shrink-0">
      <div className="ref-chat-header-inner">
        <div className="flex min-w-0 items-center gap-2">
          {onExpandSidebar ? (
            <IconButton label="Expand sidebar" onClick={onExpandSidebar} className="hidden lg:inline-flex ref-header-icon-btn">
              <IconSidebar className="h-5 w-5" />
            </IconButton>
          ) : null}
          {onOpenSidebar ? (
            <IconButton label="Open sidebar" onClick={onOpenSidebar} className="lg:hidden ref-header-icon-btn">
              <IconSidebar className="h-5 w-5" />
            </IconButton>
          ) : null}
          <div className="min-w-0 flex items-center gap-2">
            <span className="font-medium text-[15px] text-chat-fg shrink-0">AQREM Assistant</span>
            <span className="text-chat-muted hidden sm:inline" aria-hidden>
              /
            </span>
            <span className="truncate text-[15px] text-chat-muted hidden sm:inline">{conversationTitle}</span>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button type="button" className="ref-header-action-btn aq-interactive" onClick={shareLink}>
            <IconShare className="h-4 w-4" />
            <span className="hidden sm:inline">Share</span>
          </button>
          <div className="relative">
            <IconButton
              label="More options"
              className="ref-header-icon-btn"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
            >
              <IconMore />
            </IconButton>
            {menuOpen ? (
              <>
                <button type="button" className="fixed inset-0 z-30" aria-label="Close menu" onClick={() => setMenuOpen(false)} />
                <div
                  className="absolute right-0 top-full z-40 mt-1 w-44 rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer"
                  role="menu"
                >
                  <Link to="/settings" className="chat-menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                    Settings
                  </Link>
                  <Link to="/audit" className="chat-menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                    Activity
                  </Link>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}
