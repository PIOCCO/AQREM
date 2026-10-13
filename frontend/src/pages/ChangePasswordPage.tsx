import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { changePassword, loadSession } from "../lib/api";

export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const session = loadSession();
    if (!session?.token) {
      navigate("/login?next=%2Fchange-password");
      return;
    }
    const form = new FormData(e.currentTarget);
    const current_password = String(form.get("current_password"));
    const new_password = String(form.get("new_password"));
    const confirm = String(form.get("confirm_password"));
    if (new_password !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await changePassword(session, { current_password, new_password });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-canvas p-6 font-sans">
      <div className="w-full max-w-md aq-card shadow-panel aq-card-p">
        <h1 className="text-lg font-semibold mb-2">Set a new password</h1>
        <p className="text-sm text-fg-muted mb-4">Your administrator requires a password change before you continue.</p>
        <form className="space-y-3" onSubmit={onSubmit}>
          <input
            name="current_password"
            type="password"
            placeholder="Current password"
            className="aq-input"
            required
            autoComplete="current-password"
          />
          <input
            name="new_password"
            type="password"
            placeholder="New password (min 8 characters)"
            className="aq-input"
            required
            minLength={8}
            autoComplete="new-password"
          />
          <input
            name="confirm_password"
            type="password"
            placeholder="Confirm new password"
            className="aq-input"
            required
            minLength={8}
            autoComplete="new-password"
          />
          {error && <div className="aq-alert-error">{error}</div>}
          <button type="submit" disabled={loading} className="aq-btn-primary w-full">
            {loading ? "Saving…" : "Update password"}
          </button>
        </form>
      </div>
    </div>
  );
}
