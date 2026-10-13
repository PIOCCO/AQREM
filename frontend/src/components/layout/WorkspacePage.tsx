import type { ReactNode } from "react";

/** Centered workspace column for settings, activity, and similar pages. */
export default function WorkspacePage({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`workspace-page ${className}`.trim()}>{children}</div>;
}
