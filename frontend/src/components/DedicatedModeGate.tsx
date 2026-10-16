import { type ReactNode, useEffect, useState } from "react";
import { fetchDeploymentMode } from "../lib/deploymentApi";

/** Hides the multi-tenant platform console in dedicated environments (API returns 404 there too). */
export default function DedicatedModeGate({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<"loading" | "shared" | "dedicated">("loading");
  useEffect(() => {
    void fetchDeploymentMode().then((m) => setMode(m === "dedicated" ? "dedicated" : "shared"));
  }, []);
  if (mode === "loading") return null;
  if (mode === "dedicated") {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center p-6 text-center">
        <div className="max-w-md">
          <h1 className="text-lg font-semibold mb-2">Platform console not available</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            This is a dedicated environment with a single organization. Use the organization admin console at{" "}
            <a className="text-[var(--color-link)] underline" href="/org-admin">
              /org-admin
            </a>
            .
          </p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
