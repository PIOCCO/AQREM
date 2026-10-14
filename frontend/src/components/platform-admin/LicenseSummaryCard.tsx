import { licenseStatusLabel } from "../../lib/roleLabels";
import type { AdminOrganization } from "../../lib/platformAdminApi";

function statusBadgeClass(status: string) {
  if (status === "active") return "admin-badge-active";
  if (status === "test") return "admin-badge-test";
  return "admin-badge-suspended";
}

function formatDate(iso: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function LicenseSummaryCard({ org, onManageLicense }: { org: AdminOrganization; onManageLicense: () => void }) {
  const envLabel = org.environment === "test" ? "Test environment" : "Production environment";
  const renewal = formatDate(org.license_renews_at);
  const expiredOn = org.license_status === "expired" ? formatDate(org.license_expires_at) : null;

  return (
    <div className="admin-card p-4">
      <p className="text-xs text-[var(--color-text-muted)]">License</p>
      <div className="flex flex-wrap items-center gap-2 mt-2">
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadgeClass(org.license_status)}`}>
          {licenseStatusLabel(org.license_status)}
        </span>
        <span className="text-sm text-[var(--color-text-secondary)]">{envLabel}</span>
      </div>
      <p className="text-sm text-[var(--color-text-primary)] mt-3">{org.seats.seats_limit} licensed seats</p>
      <p className="text-xs text-[var(--color-text-muted)] mt-1">
        {expiredOn ? (
          <>Expired {expiredOn}</>
        ) : renewal ? (
          <>Renews {renewal}</>
        ) : (
          <>
            No renewal date set
            <button type="button" className="ml-2 text-[var(--color-link)] underline" onClick={onManageLicense}>
              Set on license tab
            </button>
          </>
        )}
      </p>
    </div>
  );
}
