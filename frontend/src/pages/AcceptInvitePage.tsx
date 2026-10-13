import { FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "../components/ui/Logo";
import { acceptInvitation, saveSession } from "../lib/api";

export default function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(token ? null : "Missing invitation token.");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      const data = await acceptInvitation({
        token,
        password: String(form.get("password")),
        full_name: String(form.get("full_name") || "") || undefined,
      });
      saveSession(data.access_token, data.organization_id ?? null);
      navigate("/");
    } catch {
      setError("Could not accept invitation. The link may be expired or already used.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-canvas p-6 font-sans">
      <div className="w-full max-w-md aq-card shadow-panel aq-card-p">
        <Logo />
        <h1 className="text-lg font-semibold mt-6 mb-2">Set your password</h1>
        <p className="text-sm text-fg-muted mb-4">Complete your AQREM account setup using your invitation.</p>
        <form className="space-y-3" onSubmit={onSubmit}>
          <input name="full_name" placeholder="Full name (optional)" className="aq-input" />
          <input
            name="password"
            type="password"
            placeholder="New password (min 8 characters)"
            className="aq-input"
            required
            minLength={8}
          />
          {error && <div className="aq-alert-error">{error}</div>}
          <button type="submit" disabled={loading || !token} className="aq-btn-primary w-full">
            {loading ? "Saving…" : "Activate account"}
          </button>
        </form>
      </div>
    </div>
  );
}
