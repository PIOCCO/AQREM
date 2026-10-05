import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchAuthMe, loadSession, type AuthSession } from "./api";
import type { UserRole } from "./roles";

type AuthUser = {
  id: string;
  email: string;
  organizationId: string;
  role: UserRole;
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
  const organizationId = localStorage.getItem("aqrem_org");
  const session = useMemo(
    () => (token && organizationId ? { token, organizationId } : null),
    [token, organizationId],
  );
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(!!session);

  async function refresh() {
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
        organizationId: me.organization_id,
        role: me.role as UserRole,
      });
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <AuthContext.Provider value={{ session, user, loading, refresh }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth requires AuthProvider");
  return ctx;
}
