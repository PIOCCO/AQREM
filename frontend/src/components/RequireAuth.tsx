import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { LoadingState } from "./ui/States";
import { clearSession, fetchAuthMe, loadSession } from "../lib/api";

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
      .then(() => {
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
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <LoadingState label="Checking session…" />
      </div>
    );
  }
  if (!valid) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
