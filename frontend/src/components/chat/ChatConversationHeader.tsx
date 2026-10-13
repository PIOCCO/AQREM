import { useState } from "react";
import { Link } from "react-router-dom";
import { IconMore, IconSidebar } from "../icons/Icons";
import { IconButton } from "../ui/IconButton";

type Props = {
  conversationTitle: string;
  /** Mobile drawer only — desktop toggle lives in the sidebar rail. */
  onOpenSidebar?: () => void;
};

export default function ChatConversationHeader({ conversationTitle, onOpenSidebar }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="ref-chat-header shrink-0">
      <div className="ref-chat-header-inner">
        <div className="flex min-w-0 items-center gap-2">
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
