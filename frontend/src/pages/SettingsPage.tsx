import { useNavigate } from "react-router-dom";
import WorkspacePage from "../components/layout/WorkspacePage";
import { CopyButton } from "../components/ui/CopyButton";
import { PageLead } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { clearSession } from "../lib/api";
import { useAuth } from "../lib/authContext";
import { useTheme, type ThemeMode } from "../lib/themeContext";

function ThemeOption({
  id,
  label,
  description,
  checked,
  onSelect,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onSelect: () => void;
}) {
  return (
    <label
      htmlFor={id}
      className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors duration-150 aq-interactive ${
        checked ? "border-[var(--color-accent)] bg-[var(--color-accent-bg)]" : "border-border bg-surface"
      }`}
    >
      <input id={id} type="radio" name="theme" className="mt-1" checked={checked} onChange={onSelect} />
      <span>
        <span className="block text-sm font-medium text-[var(--color-text-primary)]">{label}</span>
        <span className="block text-xs mt-0.5 text-[var(--color-text-muted)]">{description}</span>
      </span>
    </label>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const { mode, resolved, setMode } = useTheme();
  const navigate = useNavigate();
  const toast = useToast();

  const options: { value: ThemeMode; label: string; description: string }[] = [
    { value: "dark", label: "Dark", description: "Default AQREM appearance." },
    { value: "light", label: "Light", description: "Bright surfaces for well-lit environments." },
    { value: "system", label: "System", description: "Match your device preference." },
  ];

  function signOut() {
    clearSession();
    toast.push("Signed out");
    navigate("/login", { replace: true });
  }

  return (
    <WorkspacePage>
      <PageLead subtitle="Appearance, account details, and organization context." />
      <div className="space-y-6">
        <section className="aq-card aq-card-p" aria-labelledby="settings-appearance">
          <h2 id="settings-appearance" className="aq-section-title mb-1">
            Appearance
          </h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-4">
            Currently using <span className="font-medium text-[var(--color-text-primary)]">{resolved}</span>
            {mode === "system" ? " (system)" : ""}.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            {options.map((opt) => (
              <ThemeOption
                key={opt.value}
                id={`theme-${opt.value}`}
                label={opt.label}
                description={opt.description}
                checked={mode === opt.value}
                onSelect={() => {
                  setMode(opt.value);
                  toast.push(`Theme set to ${opt.label}`);
                }}
              />
            ))}
          </div>
        </section>

        <section className="aq-card aq-card-p max-w-2xl space-y-5 text-sm" aria-labelledby="settings-account">
          <h2 id="settings-account" className="aq-section-title">
            Account
          </h2>
          <div>
            <div className="aq-field-label">Signed in as</div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-[var(--color-text-primary)]">{user?.email ?? "—"}</span>
              {user?.email ? <CopyButton value={user.email} label="Copy email" /> : null}
            </div>
          </div>
          <div>
            <div className="aq-field-label">Role</div>
            <div className="font-medium text-[var(--color-text-primary)] capitalize">
              {user?.role?.replaceAll("_", " ") ?? "—"}
            </div>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">Role is managed by your organization administrator.</p>
          </div>
          <div>
            <div className="aq-field-label">Organization ID</div>
            <div className="flex items-start gap-2">
              <span className="font-mono text-xs break-all text-[var(--color-text-secondary)] flex-1">
                {user?.organizationId ?? "—"}
              </span>
              {user?.organizationId ? <CopyButton value={user.organizationId} label="Copy organization ID" /> : null}
            </div>
          </div>
          <div className="pt-2 border-t border-border flex flex-wrap gap-2">
            <button type="button" className="aq-btn-secondary" onClick={signOut}>
              Sign out
            </button>
          </div>
          <p className="text-xs text-[var(--color-text-muted)]">
            Organization settings are configured by an administrator. Contact them to change membership or licenses.
          </p>
        </section>
      </div>
    </WorkspacePage>
  );
}
