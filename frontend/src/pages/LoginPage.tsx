import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "../components/brand/Logo";
import { clearSession, loginUser, saveSession } from "../lib/api";

const LOGIN_ERROR_GENERIC = "Incorrect email or password.";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get("expired") === "1";
  const nextPath = searchParams.get("next") || "/";
  const emailId = useId();
  const passwordId = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(
    sessionExpired
      ? "Your session is invalid or expired (common after changing servers or ports). Please sign in again."
      : null,
  );
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (sessionExpired) clearSession();
  }, [sessionExpired]);

  useEffect(() => {
    const mode = searchParams.get("mode");
    if (mode === "register" || mode === "signup") {
      const next = new URLSearchParams(searchParams);
      next.delete("mode");
      const q = next.toString();
      navigate(q ? `/login?${q}` : "/login", { replace: true });
    }
  }, [searchParams, navigate]);

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

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
      if (data.is_platform_admin && (nextPath.includes("master-admin") || !data.organization_id)) {
        navigate("/master-admin");
      } else if (data.must_change_password) {
        navigate("/change-password");
      } else {
        navigate(nextPath.startsWith("/") ? nextPath : "/");
      }
    } catch {
      setError(LOGIN_ERROR_GENERIC);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6 font-sans">
      <div className="w-full max-w-[440px] aq-card shadow-panel aq-card-p">
        <div className="mb-6 flex flex-col items-center text-center">
          <Logo variant="mark" size={48} />
          <p className="text-[var(--color-text-muted)] mt-4 text-sm">Evidence-backed questionnaire responses</p>
        </div>
        <h1 className="text-lg font-semibold mb-4 text-[var(--color-text-primary)]">Sign in to AQREM</h1>
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <div>
            <label htmlFor={emailId} className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">
              Email
            </label>
            <input
              ref={emailRef}
              id={emailId}
              name="email"
              type="email"
              className="aq-input w-full"
              required
              autoComplete="username"
              disabled={loading}
            />
          </div>
          <div>
            <div className="flex items-center justify-between gap-2 mb-1">
              <label htmlFor={passwordId} className="text-sm font-medium text-[var(--color-text-primary)]">
                Password
              </label>
              <a
                href="/forgot-password"
                className="text-xs text-[var(--color-link)] hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
              >
                Forgot password?
              </a>
            </div>
            <div className="relative">
              <input
                id={passwordId}
                name="password"
                type={showPassword ? "text" : "password"}
                className="aq-input w-full pr-20"
                required
                autoComplete="current-password"
                disabled={loading}
              />
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-[var(--color-link)] hover:underline px-2 py-1 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)]"
                onClick={() => setShowPassword((v) => !v)}
                aria-pressed={showPassword}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>
          {error ? (
            <div className="aq-alert-error" role="alert">
              {error}
            </div>
          ) : null}
          <button type="submit" disabled={loading} className="aq-btn-primary w-full">
            {loading ? (
              <>
                <span className="aq-spinner border-t-primary-foreground border-slate-600/30" aria-hidden />
                Signing in…
              </>
            ) : (
              "Sign in"
            )}
          </button>
        </form>
        <p className="text-xs text-[var(--color-text-muted)] mt-4">
          Need access? Ask your organization admin for an invitation.
        </p>
      </div>
    </div>
  );
}
