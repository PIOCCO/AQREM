import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AuthPageShell } from "../components/auth/AuthPageShell";
import {
  acceptInvitation,
  clearSession,
  fetchAuthMe,
  loadSession,
  saveSession,
  sendAcceptInvitationVerification,
} from "../lib/api";
import { isPlatformSessionToken, resolveOrganizationIdForSession, resolvePostAuthPath } from "../lib/authRouting";
import { previewAcceptInvitation } from "../lib/joinApi";
import { roleLabel } from "../lib/roleLabels";

/** Matches backend default VERIFICATION_RESEND_COOLDOWN_SECONDS (15). */
const DEFAULT_RESEND_COOLDOWN_SEC = 15;

function readToken(searchParams: URLSearchParams, routeToken?: string): string {
  const fromQuery = searchParams.get("token")?.trim();
  if (fromQuery) return fromQuery;
  if (routeToken) return decodeURIComponent(routeToken);
  return "";
}

export default function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const { token: routeToken } = useParams<{ token?: string }>();
  const token = useMemo(() => readToken(searchParams, routeToken), [searchParams, routeToken]);
  const navigate = useNavigate();
  const [preview, setPreview] = useState<{
    organization_name: string;
    role: string;
    email: string;
    invitee_full_name: string | null;
    verification_required?: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(token ? null : "This invitation is not valid.");
  const [loading, setLoading] = useState(false);
  const [signedInEmail, setSignedInEmail] = useState<string | null>(null);
  const [platformSession, setPlatformSession] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [resendCooldownSec, setResendCooldownSec] = useState(0);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token) {
      setSignedInEmail(null);
      setPlatformSession(false);
      return;
    }
    if (isPlatformSessionToken(session.token)) {
      setPlatformSession(true);
      fetchAuthMe({ token: session.token, organizationId: null })
        .then((me) => setSignedInEmail(me.email ?? "platform administrator"))
        .catch(() => setSignedInEmail("another account"));
      return;
    }
    fetchAuthMe(session)
      .then((me) => {
        setPlatformSession(false);
        setSignedInEmail(me.email ?? null);
      })
      .catch(() => {
        clearSession();
        setSignedInEmail(null);
      });
  }, [token]);

  useEffect(() => {
    if (!token) return;
    previewAcceptInvitation(token)
      .then(setPreview)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "";
        if (/expired/i.test(msg)) setError("This invitation has expired. Ask your platform team to send a new link.");
        else if (/revoked|used|accepted/i.test(msg)) setError("This invitation is no longer valid.");
        else setError("This invitation is not valid.");
      });
  }, [token]);

  useEffect(() => {
    if (resendCooldownSec <= 0) return;
    const t = window.setInterval(() => {
      setResendCooldownSec((s) => (s <= 1 ? 0 : s - 1));
    }, 1000);
    return () => window.clearInterval(t);
  }, [resendCooldownSec]);

  const verificationRequired = preview?.verification_required !== false;

  const wrongAccount =
    preview &&
    signedInEmail &&
    (platformSession ||
      preview.email.trim().toLowerCase() !== signedInEmail.trim().toLowerCase());

  function signOutForInvite() {
    clearSession();
    setSignedInEmail(null);
    setPlatformSession(false);
    navigate(`/invite/admin/${encodeURIComponent(token)}`, { replace: true });
  }

  async function sendVerification() {
    if (!token || !preview) return;
    setSendingCode(true);
    setError(null);
    try {
      const res = await sendAcceptInvitationVerification({ token, email: preview.email });
      setCodeSent(true);
      setResendCooldownSec(DEFAULT_RESEND_COOLDOWN_SEC);
      if (res.dev_verification_code) {
        setVerificationCode(res.dev_verification_code);
      } else {
        setVerificationCode("");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not send a verification code.";
      setError(msg);
      const retry =
        err && typeof err === "object" && "retryAfterSeconds" in err
          ? (err as { retryAfterSeconds?: number }).retryAfterSeconds
          : undefined;
      if (retry && retry > 0) {
        setResendCooldownSec(retry);
      } else if (/wait|429|too many/i.test(msg)) {
        setResendCooldownSec(DEFAULT_RESEND_COOLDOWN_SEC);
      }
    } finally {
      setSendingCode(false);
    }
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!token || wrongAccount || !preview) return;
    if (verificationRequired && (!codeSent || !verificationCode.trim())) {
      setError("Verify your email with the code sent to the invited address.");
      return;
    }
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      const data = await acceptInvitation({
        token,
        email: preview.email,
        verification_code: verificationRequired ? verificationCode.trim() : "",
        password: String(form.get("password")),
        full_name: String(form.get("full_name") || preview?.invitee_full_name || "") || undefined,
      });
      const orgId = resolveOrganizationIdForSession(data.access_token, data.organization_id ?? null);
      saveSession(data.access_token, orgId);
      navigate(resolvePostAuthPath({ ...data, organization_id: orgId }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not accept invitation.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthPageShell
      title={preview ? `Join ${preview.organization_name}` : "Accept invitation"}
      subtitle={preview ? `You are invited as ${roleLabel(preview.role)}` : undefined}
    >
      {wrongAccount ? (
        <div className="aq-alert-error mb-4 space-y-3" role="alert">
          <p className="text-sm">
            You are signed in as <strong>{signedInEmail}</strong>. This invitation is for{" "}
            <strong>{preview?.email}</strong>.
          </p>
          <p className="text-sm text-chat-muted">
            Sign out to continue with the invitation. Your super admin or other sessions will not be converted into this
            organization account.
          </p>
          <button type="button" className="aq-btn-primary w-full" onClick={signOutForInvite}>
            Sign out and continue
          </button>
        </div>
      ) : null}

      {preview && !wrongAccount ? (
        <p className="text-sm text-[var(--color-text-muted)] mb-4">
          Verify <span className="text-[var(--color-text-primary)]">{preview.email}</span> and create a password. Only
          the invited inbox can complete this flow.
        </p>
      ) : null}

      {!wrongAccount ? (
        <form className="space-y-3" onSubmit={onSubmit}>
          <div>
            <label htmlFor="inv-full-name" className="text-xs font-medium">
              Full name
            </label>
            <input
              id="inv-full-name"
              name="full_name"
              className="aq-input mt-1"
              defaultValue={preview?.invitee_full_name ?? ""}
              required
            />
          </div>
          {verificationRequired ? (
            <div>
              <label htmlFor="inv-verify" className="text-xs font-medium">
                Email verification code
              </label>
              <div className="flex gap-2 mt-1">
                <input
                  id="inv-verify"
                  name="verification_code"
                  className="aq-input flex-1"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                />
                <button
                  type="button"
                  className="aq-btn-secondary shrink-0"
                  disabled={sendingCode || !preview || resendCooldownSec > 0}
                  onClick={() => void sendVerification()}
                >
                  {resendCooldownSec > 0
                    ? `Wait ${resendCooldownSec}s`
                    : codeSent
                      ? "Resend code"
                      : "Send code"}
                </button>
              </div>
            </div>
          ) : null}
          <div>
            <label htmlFor="inv-password" className="text-xs font-medium">
              New password
            </label>
            <input
              id="inv-password"
              name="password"
              type="password"
              placeholder="At least 8 characters"
              className="aq-input mt-1"
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          {error ? <div className="aq-alert-error">{error}</div> : null}
          <button type="submit" disabled={loading || !token || !preview} className="aq-btn-primary w-full">
            {loading ? "Saving…" : "Activate account"}
          </button>
        </form>
      ) : null}
    </AuthPageShell>
  );
}
