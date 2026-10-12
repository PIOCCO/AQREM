import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { fetchAuthMe, loadSession } from "../lib/api";
import { LoadingState } from "./ui/States";
import LoginPage from "../pages/LoginPage";

/** If already signed in, send users to the right home (admin vs app). */
export default function LoginEntryRedirect() {
  const session = loadSession();
  const [target, setTarget] = useState<string | null>(session?.token ? "" : null);

  useEffect(() => {
    if (!session?.token) return;
    fetchAuthMe(session)
      .then((me) => {
        if (me.is_platform_admin && !session.organizationId) {
          setTarget("/platform-admin");
        } else if (me.organization_id || session.organizationId) {
          setTarget("/");
        } else {
          setTarget(null);
        }
      })
      .catch(() => setTarget(null));
  }, [session?.token]);

  if (!session?.token) return <LoginPage />;
  if (target === "") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <LoadingState label="Checking session…" />
      </div>
    );
  }
  if (target) return <Navigate to={target} replace />;
  return <LoginPage />;
}
