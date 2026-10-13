import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { fetchAuthMe, loadSession, saveSession } from "../lib/api";
import { isPlatformSessionToken, resolveOrganizationIdForSession, resolvePostAuthPath } from "../lib/authRouting";
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
        const orgId = resolveOrganizationIdForSession(session.token, session.organizationId ?? me.organization_id ?? null);
        if (orgId && orgId !== session.organizationId) {
          saveSession(session.token, orgId);
        }
        if (isPlatformSessionToken(session.token) && !orgId) {
          setTarget("/master-admin");
        } else if (orgId || me.role === "ORG_ADMIN") {
          setTarget(
            resolvePostAuthPath({
              access_token: session.token,
              organization_id: orgId,
              role: me.role ?? null,
              is_platform_admin: me.is_platform_admin,
            }),
          );
        } else {
          setTarget(null);
        }
      })
      .catch(() => setTarget(null));
  }, [session?.token]);

  if (!session?.token) return <LoginPage />;
  if (target === "") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6">
        <LoadingState label="Checking session…" />
      </div>
    );
  }
  if (target) return <Navigate to={target} replace />;
  return <LoginPage />;
}
