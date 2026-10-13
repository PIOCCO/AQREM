import { useEffect, useState } from "react";
import { loadSession } from "../../lib/api";
import { fetchAdminOrganizations, type AdminOrganization } from "../../lib/platformAdminApi";

export default function SuperAdminUsagePage() {
  const [orgs, setOrgs] = useState<AdminOrganization[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const session = loadSession();
    if (!session?.token) return;
    fetchAdminOrganizations(session, {})
      .then((d) => setOrgs(d.items))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="admin-main-canvas p-6">
      <h2 className="text-lg font-semibold mb-2">Usage &amp; seats</h2>
      <p className="text-sm text-chat-muted mb-4">Licensed seat consumption per organization (metadata only).</p>
      {loading ? <p className="text-sm text-chat-muted">Loading…</p> : null}
      {!loading && orgs.length === 0 ? <p className="text-sm text-chat-muted">No organizations.</p> : null}
      {orgs.length > 0 ? (
        <table className="w-full text-sm admin-card overflow-hidden">
          <thead className="bg-chat-surface-subtle text-left text-xs text-chat-muted">
            <tr>
              <th className="p-3">Organization</th>
              <th className="p-3">Seats used</th>
              <th className="p-3">Limit</th>
              <th className="p-3">Available</th>
              <th className="p-3">License</th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((o) => (
              <tr key={o.id} className="border-t border-chat-border">
                <td className="p-3">{o.name}</td>
                <td className="p-3">{o.seats.seats_used}</td>
                <td className="p-3">{o.seats.seats_limit}</td>
                <td className="p-3">{o.seats.seats_available}</td>
                <td className="p-3 capitalize">{o.license_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </main>
  );
}
