import { PageHeader } from "../components/ui/States";
import { useAuth } from "../lib/authContext";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader title="Settings" subtitle="Organization and account (read-only in this MVP)." />
      <div className="aq-card aq-card-p max-w-lg space-y-5 text-sm">
        <div>
          <div className="aq-field-label">Signed in as</div>
          <div className="font-medium text-slate-900">{user?.email ?? "—"}</div>
        </div>
        <div>
          <div className="aq-field-label">Role</div>
          <div className="font-medium text-slate-900 capitalize">{user?.role?.replaceAll("_", " ") ?? "—"}</div>
        </div>
        <div>
          <div className="aq-field-label">Organization ID</div>
          <div className="font-mono text-xs break-all text-slate-700">{user?.organizationId ?? "—"}</div>
        </div>
        <p className="text-slate-600 text-xs pt-2 border-t border-border">
          User management and organization settings are configured via the API in this release. Your role controls
          which actions appear in the product.
        </p>
      </div>
    </div>
  );
}
