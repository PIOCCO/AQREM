import { Navigate } from "react-router-dom";
import { loadSession } from "../lib/api";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const session = loadSession();
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
