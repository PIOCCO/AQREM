import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
  /** For Playwright alignment checks */
  "data-testid"?: string;
};

/** Shared centered column for chat messages, empty state, scope, composer, and disclaimer. */
export default function ChatMainColumn({ children, className = "", "data-testid": testId = "chat-main-column" }: Props) {
  return (
    <div className={`chat-main-column ${className}`.trim()} data-testid={testId}>
      {children}
    </div>
  );
}
