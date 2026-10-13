import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthPageShell } from "../components/auth/AuthPageShell";
import { acceptInvitation, saveSession } from "../lib/api";
import { resolveOrganizationIdForSession, resolvePostAuthPath } from "../lib/authRouting";
import { previewAcceptInvitation } from "../lib/joinApi";
import { roleLabel } from "../lib/roleLabels";

function readInitialToken(): string {
  const params = new URLSearchParams(window.location.search);
  const t = params.get("token") ?? "";
  if (t) {
    window.history.replaceState({}, "", "/accept-invite");
  }
  return t;
}

export default function AcceptInvitePage() {
  const [token] = useState(readInitialToken);
  const navigate = useNavigate();
  const [preview, setPreview] = useState<{
    organization_name: string;
    role: string;
    email: string;
    invitee_full_name: string | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(token ? null : "This invitation is not valid.");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    previewAcceptInvitation(token)
      .then(setPreview)
      .catch(() => setError("This invitation is not valid."));
  }, [token]);

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
        full_name: String(form.get("full_name") || preview?.invitee_full_name || "") || undefined,
      });
      const orgId = resolveOrganizationIdForSession(data.access_token, data.organization_id ?? null);
      saveSession(data.access_token, orgId);
      navigate(resolvePostAuthPath({ ...data, organization_id: orgId }));
    } catch {
      setError("Could not accept invitation. The link may be expired or already used.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthPageShell
      title={preview ? `Join ${preview.organization_name}` : "Accept invitation"}
      subtitle={preview ? `You are invited as ${roleLabel(preview.role)}` : undefined}
    >
      {preview ? (
        <p className="text-sm text-[var(--color-text-muted)] mb-4">
          Signed in as <span className="text-[var(--color-text-primary)]">{preview.email}</span>
        </p>
      ) : null}
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
    </AuthPageShell>
  );
}
