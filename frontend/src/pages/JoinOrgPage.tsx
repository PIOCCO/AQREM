import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthPageShell } from "../components/auth/AuthPageShell";
import { completeJoin, previewJoin, startJoin, verifyJoinEmail } from "../lib/joinApi";
import { saveSession } from "../lib/api";

type Step = "details" | "verify" | "password" | "done";

function readInitialToken(): string {
  const params = new URLSearchParams(window.location.search);
  const t = params.get("token") ?? "";
  if (t) {
    window.history.replaceState({}, "", "/join");
  }
  return t;
}

export default function JoinOrgPage() {
  const navigate = useNavigate();
  const [token] = useState(readInitialToken);
  const [orgName, setOrgName] = useState<string | null>(null);
  const [step, setStep] = useState<Step>("details");
  const [pendingId, setPendingId] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [doneMessage, setDoneMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("This link is not valid. Ask your administrator for a new one.");
      return;
    }
    previewJoin(token)
      .then((p) => setOrgName(p.organization_name))
      .catch(() => setError("This link is not valid. Ask your administrator for a new one."));
  }, [token]);

  async function onDetails(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      const res = await startJoin({
        token,
        email: String(form.get("email")),
        full_name: String(form.get("full_name")),
      });
      setPendingId(res.pending_id);
      setDevCode(res.dev_verification_code ?? null);
      setStep("verify");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not continue");
    } finally {
      setLoading(false);
    }
  }

  async function onVerify(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      await verifyJoinEmail({
        token,
        pending_id: pendingId,
        code: String(form.get("code")),
      });
      setStep("password");
    } catch {
      setError("That code is not valid. Check your email and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function onPassword(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      const res = await completeJoin({
        token,
        pending_id: pendingId,
        password: String(form.get("password")),
      });
      if (res.status === "pending_approval") {
        setDoneMessage("Your request was sent to your company administrator for approval.");
        setStep("done");
        return;
      }
      if (res.access_token && res.organization_id) {
        saveSession(res.access_token, res.organization_id);
        navigate("/");
        return;
      }
      setStep("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finish setup");
    } finally {
      setLoading(false);
    }
  }

  const title =
    step === "done"
      ? "Request submitted"
      : orgName
        ? `Join ${orgName}`
        : "Join your organization";

  return (
    <AuthPageShell title={title} subtitle="Employee access">
      {error ? <div className="aq-alert-error mb-3">{error}</div> : null}
      {step === "details" && orgName && !error ? (
        <form className="space-y-3" onSubmit={onDetails}>
          <div>
            <label htmlFor="join-name" className="text-xs font-medium">
              Full name
            </label>
            <input id="join-name" name="full_name" className="aq-input mt-1" required autoComplete="name" />
          </div>
          <div>
            <label htmlFor="join-email" className="text-xs font-medium">
              Work email
            </label>
            <input id="join-email" name="email" type="email" className="aq-input mt-1" required autoComplete="email" />
          </div>
          <button type="submit" className="aq-btn-primary w-full" disabled={loading}>
            {loading ? "Sending code…" : "Continue"}
          </button>
        </form>
      ) : null}
      {step === "verify" ? (
        <form className="space-y-3" onSubmit={onVerify}>
          <p className="text-sm text-[var(--color-text-muted)]">
            Enter the verification code sent to your work email.
          </p>
          {devCode ? (
            <p className="text-xs text-[var(--color-text-muted)] border border-chat-border rounded p-2">
              Test environment code: <span className="font-mono">{devCode}</span>
            </p>
          ) : null}
          <div>
            <label htmlFor="join-code" className="text-xs font-medium">
              Verification code
            </label>
            <input id="join-code" name="code" className="aq-input mt-1" required inputMode="numeric" autoComplete="one-time-code" />
          </div>
          <button type="submit" className="aq-btn-primary w-full" disabled={loading}>
            {loading ? "Verifying…" : "Verify email"}
          </button>
        </form>
      ) : null}
      {step === "password" ? (
        <form className="space-y-3" onSubmit={onPassword}>
          <div>
            <label htmlFor="join-password" className="text-xs font-medium">
              Choose a password
            </label>
            <input
              id="join-password"
              name="password"
              type="password"
              className="aq-input mt-1"
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          <button type="submit" className="aq-btn-primary w-full" disabled={loading}>
            {loading ? "Creating account…" : "Join organization"}
          </button>
        </form>
      ) : null}
      {step === "done" && doneMessage ? (
        <p className="text-sm text-[var(--color-text-primary)]">{doneMessage}</p>
      ) : null}
    </AuthPageShell>
  );
}
