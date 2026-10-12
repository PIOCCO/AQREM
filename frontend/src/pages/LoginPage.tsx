import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "../components/ui/Logo";
import { clearSession, loginUser, saveSession } from "../lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get("expired") === "1";
  const nextPath = searchParams.get("next") || "/";
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
      const data = await loginUser({
        email: String(form.get("email")),
        password: String(form.get("password")),
      });
      saveSession(data.access_token, data.organization_id ?? null);
      if (data.is_platform_admin && (nextPath === "/platform-admin" || !data.organization_id)) {
        navigate("/platform-admin");
      } else if (data.must_change_password) {
        navigate("/change-password");
      } else {
        navigate(nextPath.startsWith("/") ? nextPath : "/");
      }
    } catch {
      setError("Authentication failed. Check your credentials and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-canvas p-6 font-sans">
      <div className="w-full max-w-md aq-card shadow-panel aq-card-p">
        <div className="mb-6">
          <Logo />
          <p className="text-slate-600 mt-3 text-sm">Evidence-backed questionnaire responses</p>
        </div>
        <h1 className="text-lg font-semibold mb-4">Sign in</h1>
        <form className="space-y-3" onSubmit={onSubmit}>
          <input name="email" type="email" placeholder="Email" className="aq-input" required autoComplete="username" />
          <input
            name="password"
            type="password"
            placeholder="Password"
            className="aq-input"
            required
            autoComplete="current-password"
          />
          {error && <div className="aq-alert-error">{error}</div>}
          <button type="submit" disabled={loading} className="aq-btn-primary w-full">
            {loading ? (
              <>
                <span className="aq-spinner border-t-primary-foreground border-slate-600/30" aria-hidden />
                Please wait…
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>
        <p className="text-xs text-slate-500 mt-4">
          Access is provisioned by your administrator. If you received an invitation link, use that URL to set your
          password.
        </p>
        <p className="text-xs text-slate-500 mt-2">
          Platform administrators: sign in with your admin account (from{" "}
          <code className="text-[11px]">PLATFORM_ADMIN_EMAIL</code>), then open{" "}
          <a href="/platform-admin" className="text-chat-accent hover:underline">
            /platform-admin
          </a>
          .
        </p>
      </div>
    </div>
  );
}
