import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchAuthMe, loadSession, type AuthSession } from "./api";
import { normalizeOrganizationId } from "./uuid";
import type { UserRole } from "./roles";

type AuthUser = {
  id: string;
  email: string;
  fullName: string;
  organizationId: string | null;
  role: UserRole | null;
  isPlatformAdmin: boolean;
  permissions: string[];
};

type AuthContextValue = {
  session: AuthSession | null;
  user: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const token = localStorage.getItem("aqrem_token");
  const organizationId = normalizeOrganizationId(localStorage.getItem("aqrem_org"));
  const session = useMemo(
    () => (token ? { token, organizationId } : null),
    [token, organizationId],
  );
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(!!session);

  const refresh = useCallback(async () => {
    const s = loadSession();
    if (!s) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await fetchAuthMe(s);
      setUser({
        id: me.id,
        email: me.email,
        fullName: me.full_name,
        organizationId: me.organization_id ?? null,
        role: (me.role as UserRole) ?? null,
        isPlatformAdmin: Boolean(me.is_platform_admin),
        permissions: Array.isArray(me.permissions) ? me.permissions : [],
      });
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    function onFocus() {
      void refresh();
    }
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(() => void refresh(), 60_000);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ session, user, loading, refresh }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth requires AuthProvider");
  return ctx;
}
