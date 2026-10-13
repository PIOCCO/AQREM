import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { AuthProvider } from "../lib/authContext";
import { LoadingState } from "./ui/States";
import { clearSession, fetchAuthMe, loadSession, saveSession } from "../lib/api";
import { isPlatformSessionToken, organizationIdFromToken, resolveOrganizationIdForSession } from "../lib/authRouting";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [valid, setValid] = useState(false);
  const [redirectTo, setRedirectTo] = useState<string | null>(null);

  useEffect(() => {
    const session = loadSession();
    if (!session) {
      setValid(false);
      setReady(true);
      return;
    }
    fetchAuthMe(session)
      .then((me) => {
        const orgId =
          resolveOrganizationIdForSession(session.token, session.organizationId) ??
          resolveOrganizationIdForSession(session.token, me.organization_id ?? null);
        if (orgId && orgId !== session.organizationId) {
          saveSession(session.token, orgId);
        }

        const platformToken = isPlatformSessionToken(session.token);
        if (platformToken && !orgId) {
          setRedirectTo("/master-admin");
          setValid(false);
          setReady(true);
          return;
        }
        if (!platformToken && !orgId && !organizationIdFromToken(session.token)) {
          setValid(false);
          setReady(true);
          return;
        }
        if (me.must_change_password && !window.location.pathname.startsWith("/change-password")) {
          window.location.assign("/change-password");
          return;
        }
        setValid(true);
        setReady(true);
      })
      .catch(() => {
        clearSession();
        setValid(false);
        setReady(true);
      });
  }, []);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6">
        <LoadingState label="Checking session…" />
      </div>
    );
  }
  if (redirectTo) return <Navigate to={redirectTo} replace />;
  if (!valid) return <Navigate to="/login" replace />;
  return <AuthProvider>{children}</AuthProvider>;
}
