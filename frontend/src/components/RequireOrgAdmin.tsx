import { ReactNode, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { clearSession, fetchAuthMeTenant, loadSession } from "../lib/api";
import { hasAdminConsoleAccess } from "../lib/permissions";
import { recordAdminConsoleEnter } from "../lib/orgAdminApi";
import AdminAccessDenied from "../pages/AdminAccessDenied";
import { LoadingState } from "./ui/States";

export default function RequireOrgAdmin({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function verify() {
      const session = loadSession();
      if (!session?.token || !session.organizationId) {
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
          const orgId = session.organizationId ?? "";
          const throttleKey = `aqrem:admin-console-enter:${orgId}`;
          const last = sessionStorage.getItem(throttleKey);
          const now = Date.now();
          const fifteenMin = 15 * 60 * 1000;
          if (!last || now - Number(last) >= fifteenMin) {
            try {
              await recordAdminConsoleEnter(session);
              sessionStorage.setItem(throttleKey, String(now));
            } catch {
              /* audit failure must not block access after server verified role */
            }
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
  }, []);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6">
        <LoadingState label="Verifying admin access…" />
      </div>
    );
  }

  if (!signedIn) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }

  if (!allowed) {
    return <AdminAccessDenied />;
  }

  return <>{children}</>;
}
