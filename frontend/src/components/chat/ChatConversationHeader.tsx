import { useState } from "react";
import { Link } from "react-router-dom";
import { IconChevronDown, IconMore, IconShare, IconSidebar } from "../icons/Icons";
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
            <button type="button" className="ref-header-icon-btn hidden lg:inline-flex" onClick={onExpandSidebar} aria-label="Expand sidebar">
              <IconSidebar className="h-5 w-5" />
            </button>
          ) : null}
          {onOpenSidebar ? (
            <button type="button" className="ref-header-icon-btn lg:hidden" onClick={onOpenSidebar} aria-label="Open sidebar">
              <IconSidebar className="h-5 w-5" />
            </button>
          ) : null}
          <button type="button" className="ref-header-assistant-btn" aria-haspopup="listbox">
            <span className="font-medium text-[15px] text-chat-fg">AQREM Assistant</span>
            <IconChevronDown className="h-4 w-4 text-chat-muted" />
          </button>
          <span className="text-chat-muted hidden sm:inline">/</span>
          <span className="truncate text-[15px] text-chat-muted hidden sm:inline">{conversationTitle}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button type="button" className="ref-header-action-btn" onClick={shareLink}>
            <IconShare className="h-4 w-4" />
            <span className="hidden sm:inline">Share</span>
          </button>
          <div className="relative">
            <button
              type="button"
              className="ref-header-icon-btn"
              aria-label="More options"
              onClick={() => setMenuOpen((v) => !v)}
            >
              <IconMore />
            </button>
            {menuOpen ? (
              <>
                <button type="button" className="fixed inset-0 z-30" aria-label="Close" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-full z-40 mt-1 w-44 rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer">
                  <Link to="/settings" className="chat-menu-item" onClick={() => setMenuOpen(false)}>
                    Settings
                  </Link>
                  <Link to="/audit" className="chat-menu-item" onClick={() => setMenuOpen(false)}>
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
