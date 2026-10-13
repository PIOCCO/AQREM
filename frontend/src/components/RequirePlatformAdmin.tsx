import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { clearSession, fetchAuthMe, loadSession } from "../lib/api";
import { LoadingState } from "./ui/States";

export default function RequirePlatformAdmin({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token) {
      setReady(true);
      return;
    }
    fetchAuthMe(session)
      .then((me) => {
        const perms: string[] = Array.isArray(me.permissions) ? me.permissions : [];
        setAllowed(Boolean(me.is_platform_admin) || perms.includes("org:read"));
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
        <LoadingState label="Checking administrator session…" />
      </div>
    );
  }
  if (!loadSession()?.token || !allowed) {
    return <Navigate to="/login?next=%2Fmaster-admin" replace />;
  }
  return <>{children}</>;
}
