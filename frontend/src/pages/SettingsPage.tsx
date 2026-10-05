import { PageHeader } from "../components/ui/States";
import { useAuth } from "../lib/authContext";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader title="Settings" subtitle="Organization and account (read-only in this MVP)." />
      <div className="rounded-xl border border-slate-200 bg-white p-6 max-w-lg space-y-4 text-sm">
        <div>
          <div className="text-slate-500">Signed in as</div>
          <div className="font-medium">{user?.email ?? "—"}</div>
        </div>
        <div>
          <div className="text-slate-500">Role</div>
          <div className="font-medium">{user?.role ?? "—"}</div>
        </div>
        <div>
          <div className="text-slate-500">Organization ID</div>
          <div className="font-mono text-xs break-all">{user?.organizationId ?? "—"}</div>
        </div>
        <p className="text-slate-600 text-xs pt-2">
          User management and organization settings are configured via the API in this release. Your role controls
          which actions appear in the product.
        </p>
      </div>
    </div>
  );
}
