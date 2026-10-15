import type { ReactNode } from "react";
import ChatMainColumn from "./ChatMainColumn";

type Props = {
  scopePicker?: ReactNode;
  notice?: ReactNode;
  children: ReactNode;
};

/** Pinned footer: scope chip, composer, and disclaimer share the main chat column. */
export default function ChatComposerDock({ scopePicker, notice, children }: Props) {
  return (
    <div className="ref-composer-dock shrink-0 min-w-0" data-testid="chat-composer-dock">
      <ChatMainColumn className="chat-composer-column" data-testid="chat-composer-column">
        {scopePicker ? <div className="chat-scope-row">{scopePicker}</div> : null}
        {notice}
        {children}
      </ChatMainColumn>
    </div>
  );
}
