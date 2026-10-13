import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Logo } from "../components/brand/Logo";
import { resetPasswordWithToken } from "../lib/api";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) {
      setError("This reset link is invalid. Request a new one from the sign-in page.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await resetPasswordWithToken(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] p-6 font-sans">
      <div className="w-full max-w-[440px] aq-card shadow-panel aq-card-p">
        <div className="mb-6 flex flex-col items-center text-center">
          <Logo variant="mark" size={48} />
        </div>
        <h1 className="text-lg font-semibold mb-4">Choose a new password</h1>
        {done ? (
          <p className="text-sm text-[var(--color-text-muted)]">
            Your password was updated.{" "}
            <Link to="/login" className="text-[var(--color-link)] hover:underline">
              Sign in
            </Link>
          </p>
        ) : (
          <form className="space-y-4" onSubmit={onSubmit}>
            <div>
              <label htmlFor="new-password" className="block text-sm font-medium mb-1">
                New password
              </label>
              <input
                id="new-password"
                type="password"
                className="aq-input w-full"
                minLength={8}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            {error ? (
              <div className="aq-alert-error" role="alert">
                {error}
              </div>
            ) : null}
            <button type="submit" className="aq-btn-primary w-full" disabled={loading}>
              {loading ? "Saving…" : "Update password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
