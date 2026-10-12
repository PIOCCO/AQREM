import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { clearSession, fetchAuthMeTenant, loadSession } from "../lib/api";
import { canManageOrg } from "../lib/roles";
import type { UserRole } from "../lib/roles";
import { LoadingState } from "./ui/States";

export default function RequireOrgAdmin({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token || !session.organizationId) {
      setReady(true);
      return;
    }
    fetchAuthMeTenant(session)
      .then((me) => {
        setAllowed(canManageOrg((me.role as UserRole) ?? "VIEWER"));
        setReady(true);
      })
      .catch(() => {
        clearSession();
        setReady(true);
      });
  }, []);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <LoadingState label="Checking organization admin access…" />
      </div>
    );
  }
  if (!loadSession()?.organizationId || !allowed) {
    return <Navigate to="/login?next=%2Fadmin" replace />;
  }
  return <>{children}</>;
}
