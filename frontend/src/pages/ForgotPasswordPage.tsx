import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../components/brand/Logo";
import { requestPasswordReset } from "../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const res = await requestPasswordReset(email.trim());
      setMessage(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
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
        <h1 className="text-lg font-semibold mb-2">Reset your password</h1>
        <p className="text-sm text-[var(--color-text-muted)] mb-4">
          Enter your work email. If an account exists, we will send a reset link.
        </p>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div>
            <label htmlFor="reset-email" className="block text-sm font-medium mb-1">
              Email
            </label>
            <input
              id="reset-email"
              type="email"
              className="aq-input w-full"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
          </div>
          {message ? (
            <div className="text-sm rounded px-3 py-2 bg-[var(--admin-status-active-bg)] text-[var(--admin-status-active-text)]" role="status">
              {message}
            </div>
          ) : null}
          {error ? (
            <div className="aq-alert-error" role="alert">
              {error}
            </div>
          ) : null}
          <button type="submit" className="aq-btn-primary w-full" disabled={loading}>
            {loading ? "Sending…" : "Send reset link"}
          </button>
        </form>
        <p className="text-sm mt-4">
          <Link to="/login" className="text-[var(--color-link)] hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
