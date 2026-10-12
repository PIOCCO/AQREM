import { PageLead } from "../components/ui/States";
import { useAuth } from "../lib/authContext";
import { useTheme, type ThemeMode } from "../lib/themeContext";
import WorkspacePage from "../components/layout/WorkspacePage";

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
      className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors ${
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

  const options: { value: ThemeMode; label: string; description: string }[] = [
    { value: "dark", label: "Dark", description: "Default AQREM appearance. Easier on the eyes in low light." },
    { value: "light", label: "Light", description: "Bright surfaces for well-lit environments." },
    { value: "system", label: "System", description: "Follow your device light or dark preference." },
  ];

  return (
    <WorkspacePage>
      <PageLead subtitle="Appearance, account details, and organization context." />
      <div className="space-y-6">
        <section className="aq-card aq-card-p" aria-labelledby="settings-appearance">
          <h2 id="settings-appearance" className="aq-section-title mb-1">
            Appearance
          </h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-4">
            Currently using <span className="font-medium text-[var(--color-text-primary)]">{resolved}</span> theme
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
                onSelect={() => setMode(opt.value)}
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
            <div className="font-medium text-[var(--color-text-primary)]">{user?.email ?? "—"}</div>
          </div>
          <div>
            <div className="aq-field-label">Role</div>
            <div className="font-medium text-[var(--color-text-primary)] capitalize">
              {user?.role?.replaceAll("_", " ") ?? "—"}
            </div>
          </div>
          <div>
            <div className="aq-field-label">Organization ID</div>
            <div className="font-mono text-xs break-all text-[var(--color-text-secondary)]">
              {user?.organizationId ?? "—"}
            </div>
          </div>
          <p className="text-xs pt-2 border-t border-border text-[var(--color-text-muted)]">
            User management and organization settings are configured via the API in this release. Your role controls
            which actions appear in the product.
          </p>
        </section>
      </div>
    </WorkspacePage>
  );
}
