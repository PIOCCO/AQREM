import { useEffect, useState } from "react";
import { useAuth } from "../../lib/authContext";
import { fetchLicenseStatus, licenseBannerFor, type LicenseBanner as Banner } from "../../lib/licenseStatus";

/** Dedicated tier: license warning / grace / read-only notice. Renders nothing otherwise. */
export default function LicenseBanner() {
  const { session } = useAuth();
  const [banner, setBanner] = useState<Banner | null>(null);

  useEffect(() => {
    if (!session?.organizationId) return;
    let cancelled = false;
    const load = () =>
      fetchLicenseStatus(session).then((s) => {
        if (!cancelled) setBanner(licenseBannerFor(s));
      });
    void load();
    const timer = window.setInterval(load, 5 * 60 * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [session]);

  if (!banner) return null;
  const tone =
    banner.tone === "danger"
      ? "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100"
      : "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100";
  return (
    <div role="status" data-testid="license-banner" className={`shrink-0 border-b px-4 py-2 text-sm ${tone}`}>
      <strong className="mr-2">{banner.title}:</strong>
      <span>{banner.text}</span>
    </div>
  );
}
