import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { AuthProvider } from "../lib/authContext";
import { LoadingState } from "./ui/States";
import { clearSession, fetchAuthMe, loadSession, saveSession } from "../lib/api";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [valid, setValid] = useState(false);

  useEffect(() => {
    const session = loadSession();
    if (!session) {
      setValid(false);
      setReady(true);
      return;
    }
    fetchAuthMe(session)
      .then((me) => {
        if (me.is_platform_admin && !session.organizationId) {
          setValid(false);
          setReady(true);
          return;
        }
        if (!me.is_platform_admin && !session.organizationId && !me.organization_id) {
          setValid(false);
          setReady(true);
          return;
        }
        if (!session.organizationId && me.organization_id) {
          saveSession(session.token, me.organization_id);
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
  if (!valid) return <Navigate to="/login" replace />;
  return <AuthProvider>{children}</AuthProvider>;
}
