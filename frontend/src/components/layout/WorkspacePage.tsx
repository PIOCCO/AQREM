import type { ReactNode } from "react";

/** Centered workspace column (960px) for settings, activity, and similar pages. */
export default function WorkspacePage({ children }: { children: ReactNode }) {
  return <div className="workspace-page">{children}</div>;
}
