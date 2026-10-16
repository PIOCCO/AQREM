import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthPageShell } from "../components/auth/AuthPageShell";
import { createFirstAdmin, fetchSetupStatus, type SetupStatus } from "../lib/deploymentApi";

/** Dedicated environments only: create the first organization administrator. */
export default function DedicatedSetupPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void fetchSetupStatus().then((s) => {
      setStatus(s);
      if (!s || s.deployment_mode !== "dedicated" || !s.setup_required) navigate("/login", { replace: true });
    });
  }, [navigate]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    const password = String(form.get("password") ?? "");
    if (password !== String(form.get("password2") ?? "")) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 12) {
      setError("Use at least 12 characters for the password.");
      return;
    }
    setLoading(true);
    try {
      await createFirstAdmin({
        setup_token: String(form.get("setup_token") ?? ""),
        email: String(form.get("email") ?? ""),
        full_name: String(form.get("full_name") ?? ""),
        password,
        organization_name: String(form.get("organization_name") ?? "") || undefined,
      });
      navigate("/login?setup=done", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthPageShell title="Set up your AQREM environment" subtitle="Create the first administrator">
      {status && !status.setup_token_configured ? (
        <p className="text-sm text-[var(--color-danger,#b91c1c)] mb-3">
          This environment has no SETUP_TOKEN configured. Ask your operator to set it, then reload.
        </p>
      ) : null}
      {status?.license_state && status.license_state !== "valid" ? (
        <p className="text-sm text-[var(--color-warning,#b45309)] mb-3" role="status">
          License: {status.license_message}
        </p>
      ) : null}
      <form className="space-y-3" onSubmit={onSubmit} noValidate>
        <Field name="organization_name" label="Organization name" defaultValue={status?.organization_name ?? ""} />
        <Field name="full_name" label="Your name" required />
        <Field name="email" label="Email" type="email" required autoComplete="username" />
        <Field name="password" label="Password (12+ characters)" type="password" required autoComplete="new-password" />
        <Field name="password2" label="Confirm password" type="password" required autoComplete="new-password" />
        <Field name="setup_token" label="Setup token (from your operator)" type="password" required />
        {error ? (
          <p role="alert" className="text-sm text-[var(--color-danger,#b91c1c)]">
            {error}
          </p>
        ) : null}
        <button type="submit" className="aq-btn aq-btn-primary w-full" disabled={loading}>
          {loading ? "Creating…" : "Create administrator"}
        </button>
      </form>
    </AuthPageShell>
  );
}

function Field(props: {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  defaultValue?: string;
  autoComplete?: string;
}) {
  const id = `setup-${props.name}`;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">
        {props.label}
      </label>
      <input
        id={id}
        name={props.name}
        type={props.type ?? "text"}
        required={props.required}
        defaultValue={props.defaultValue}
        autoComplete={props.autoComplete}
        className="aq-input w-full"
      />
    </div>
  );
}
