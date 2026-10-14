import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { AuthProvider } from "../lib/authContext";
import { clearSession, fetchAuthMe, loadSession, saveSession } from "../lib/api";
import {
  isPlatformSessionToken,
  isTenantSessionToken,
  ORG_ADMIN_BASE,
  resolveOrganizationIdForSession,
  SUPER_ADMIN_BASE,
} from "../lib/authRouting";
import { hasAdminConsoleAccess } from "../lib/permissions";
import { LoadingState } from "./ui/States";

/**
 * L2/L3 tenant workspace guard — rejects platform-only JWTs (no customer data via L1 token).
 */
export default function RequireTenantWorkspace({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [valid, setValid] = useState(false);
  const [redirectTo, setRedirectTo] = useState<string | null>(null);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token) {
      setValid(false);
      setReady(true);
      return;
    }
    if (isPlatformSessionToken(session.token)) {
      setRedirectTo(SUPER_ADMIN_BASE);
      setValid(false);
      setReady(true);
      return;
    }
    if (!isTenantSessionToken(session.token)) {
      clearSession();
      setValid(false);
      setReady(true);
      return;
    }

    const orgId = resolveOrganizationIdForSession(session.token, session.organizationId);
    if (!orgId) {
      setValid(false);
      setReady(true);
      return;
    }
    if (orgId !== session.organizationId) {
      saveSession(session.token, orgId);
    }

    fetchAuthMe({ token: session.token, organizationId: orgId })
      .then((me) => {
        if (me.must_change_password && !window.location.pathname.startsWith("/change-password")) {
          window.location.assign("/change-password");
          return;
        }
        if (
          (hasAdminConsoleAccess(me.permissions) || me.role === "ORG_ADMIN") &&
          !window.location.pathname.startsWith(ORG_ADMIN_BASE) &&
          !window.location.pathname.startsWith("/admin")
        ) {
          setRedirectTo(ORG_ADMIN_BASE);
          setValid(false);
          setReady(true);
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
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6" data-app="tenant-loading">
        <LoadingState label="Checking session…" />
      </div>
    );
  }
  if (redirectTo) return <Navigate to={redirectTo} replace />;
  if (!valid) return <Navigate to="/login" replace />;
  return (
    <div data-app="tenant-workspace">
      <AuthProvider>{children}</AuthProvider>
    </div>
  );
}
