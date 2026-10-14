import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { clearSession, fetchAuthMe, fetchAuthMePlatform, loadSession, saveSession } from "../lib/api";
import {
  isPlatformSessionToken,
  isTenantSessionToken,
  ORG_ADMIN_BASE,
  SUPER_ADMIN_BASE,
} from "../lib/authRouting";
import { hasAdminConsoleAccess } from "../lib/permissions";
import { LoadingState } from "./ui/States";

/**
 * L1 platform console guard — requires a platform JWT (aud=aqrem-master), not tenant membership alone.
 */
export default function RequireSuperAdmin({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [redirectTo, setRedirectTo] = useState<string | null>(null);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token) {
      setReady(true);
      return;
    }
    if (!isPlatformSessionToken(session.token)) {
      if (isTenantSessionToken(session.token)) {
        fetchAuthMe(session)
          .then((me) => {
            if (hasAdminConsoleAccess(me.permissions) || me.role === "ORG_ADMIN") {
              setRedirectTo(ORG_ADMIN_BASE);
            } else {
              setRedirectTo("/");
            }
          })
          .catch(() => setRedirectTo("/"))
          .finally(() => setReady(true));
        return;
      }
      setAllowed(false);
      setReady(true);
      return;
    }
    saveSession(session.token, null);
    fetchAuthMePlatform({ token: session.token, organizationId: null })
      .then((me) => {
        const perms: string[] = Array.isArray(me.permissions) ? me.permissions : [];
        const platformStaff = Boolean(me.platform_role) || perms.includes("org:read");
        setAllowed(platformStaff);
        setReady(true);
      })
      .catch(() => {
        clearSession();
        setReady(true);
      });
  }, []);

  if (redirectTo) return <Navigate to={redirectTo} replace />;

  if (!ready) {
    return (
      <div
        className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6"
        data-app="super-admin-loading"
      >
        <LoadingState label="Checking platform session…" />
      </div>
    );
  }
  if (!loadSession()?.token || !allowed) {
    return <Navigate to={`/login?next=${encodeURIComponent(SUPER_ADMIN_BASE)}`} replace />;
  }
  return <div data-app="super-admin">{children}</div>;
}
