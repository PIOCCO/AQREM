import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { clearSession } from "../lib/api";
import { loginUser, registerUser, saveSession } from "../lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get("expired") === "1";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(
    sessionExpired
      ? "Your session is invalid or expired (common after changing servers or ports). Please sign in again."
      : null,
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (sessionExpired) clearSession();
  }, [sessionExpired]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      if (mode === "register") {
        const data = await registerUser({
          email: String(form.get("email")),
          password: String(form.get("password")),
          full_name: String(form.get("full_name")),
          organization_name: String(form.get("organization_name")),
        });
        saveSession(data.access_token, data.organization_id);
      } else {
        const data = await loginUser({
          email: String(form.get("email")),
          password: String(form.get("password")),
        });
        saveSession(data.access_token, data.organization_id);
      }
      navigate("/");
    } catch {
      setError("Authentication failed. Check your credentials and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-muted p-6">
      <div className="w-full max-w-md aq-card shadow-card aq-card-p">
        <h1 className="aq-page-title mb-1">AQREM</h1>
        <p className="text-slate-600 mb-6">Evidence-backed questionnaire responses</p>
        <div className="flex gap-2 mb-6 p-1 rounded-md bg-surface-subtle">
          <button
            type="button"
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${mode === "login" ? "bg-primary text-primary-foreground" : "text-slate-700 hover:bg-surface"}`}
            onClick={() => setMode("login")}
          >
            Sign in
          </button>
          <button
            type="button"
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${mode === "register" ? "bg-primary text-primary-foreground" : "text-slate-700 hover:bg-surface"}`}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>
        <form className="space-y-3" onSubmit={onSubmit}>
          {mode === "register" && (
            <>
              <input name="full_name" placeholder="Full name" className="aq-input" required />
              <input name="organization_name" placeholder="Organization name" className="aq-input" required />
            </>
          )}
          <input name="email" type="email" placeholder="Email" className="aq-input" required />
          <input name="password" type="password" placeholder="Password" className="aq-input" required />
          {error && <div className="aq-alert-error">{error}</div>}
          <button type="submit" disabled={loading} className="aq-btn-primary w-full">
            {loading ? (
              <>
                <span className="aq-spinner border-t-primary-foreground border-slate-600/30" aria-hidden />
                Please wait…
              </>
            ) : mode === "login" ? (
              "Sign in"
            ) : (
              "Create account"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
