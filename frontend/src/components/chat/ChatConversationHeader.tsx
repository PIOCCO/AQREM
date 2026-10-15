import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { IconMore, IconShare, IconSidebar } from "../icons/Icons";
import { IconButton } from "../ui/IconButton";
import type { AuthSession } from "../../lib/api";
import type { ChatConversation } from "../../lib/conversations";
import { PRODUCT_V1 } from "../../lib/productV1";
import ShareConversationDialog from "./ShareConversationDialog";

type Props = {
  conversationTitle: string;
  /** Mobile drawer only — desktop toggle lives in the sidebar rail. */
  onOpenSidebar?: () => void;
  session?: AuthSession | null;
  conversation?: ChatConversation | null;
};

export default function ChatConversationHeader({
  conversationTitle,
  onOpenSidebar,
  session,
  conversation,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const shareBtnRef = useRef<HTMLButtonElement>(null);

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
        {PRODUCT_V1 ? null : (
          <div className="flex items-center gap-1 shrink-0">
            <button
              ref={shareBtnRef}
              type="button"
              className="ref-header-action-btn aq-interactive"
              aria-haspopup="dialog"
              aria-expanded={shareOpen}
              onClick={() => setShareOpen(true)}
            >
              <IconShare className="h-4 w-4" />
              <span className="hidden sm:inline">Share</span>
            </button>
            {session ? (
              <ShareConversationDialog
                open={shareOpen}
                onClose={() => setShareOpen(false)}
                session={session}
                conversation={conversation ?? null}
                anchorRef={shareBtnRef}
              />
            ) : null}
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
        )}
      </div>
    </header>
  );
}
