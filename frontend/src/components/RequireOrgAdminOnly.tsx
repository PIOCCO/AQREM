import { ReactNode, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { clearSession, fetchAuthMeTenant, loadSession } from "../lib/api";
import { isPlatformSessionToken, isTenantSessionToken, SUPER_ADMIN_BASE } from "../lib/authRouting";
import { hasAdminConsoleAccess } from "../lib/permissions";
import { recordAdminConsoleEnter } from "../lib/orgAdminApi";
import AdminAccessDenied from "../pages/AdminAccessDenied";
import { LoadingState } from "./ui/States";

/** Customer organization admin console (L2) — tenant JWT + admin_console permission only. */
export default function RequireOrgAdminOnly({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [wrongSurface, setWrongSurface] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function verify() {
      const session = loadSession();
      if (!session?.token) {
        if (!cancelled) {
          setSignedIn(false);
          setAllowed(false);
          setReady(true);
        }
        return;
      }
      if (isPlatformSessionToken(session.token)) {
        if (!cancelled) {
          setWrongSurface(SUPER_ADMIN_BASE);
          setReady(true);
        }
        return;
      }
      if (!isTenantSessionToken(session.token) || !session.organizationId) {
        if (!cancelled) {
          setSignedIn(false);
          setAllowed(false);
          setReady(true);
        }
        return;
      }
      setSignedIn(true);
      try {
        const me = await fetchAuthMeTenant(session);
        const ok = hasAdminConsoleAccess(me.permissions);
        if (!cancelled) {
          setAllowed(ok);
          setReady(true);
        }
        if (ok) {
          try {
            await recordAdminConsoleEnter(session);
          } catch {
            /* non-blocking */
          }
        }
      } catch {
        clearSession();
        if (!cancelled) {
          setSignedIn(false);
          setAllowed(false);
          setReady(true);
        }
      }
    }
    setReady(false);
    void verify();
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6" data-app="org-admin-loading">
        <LoadingState label="Verifying admin access…" />
      </div>
    );
  }
  if (wrongSurface) return <Navigate to={wrongSurface} replace />;
  if (!signedIn) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  if (!allowed) return <AdminAccessDenied />;
  return <div data-app="org-admin">{children}</div>;
}
