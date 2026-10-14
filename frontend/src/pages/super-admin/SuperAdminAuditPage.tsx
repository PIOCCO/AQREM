import { Link } from "react-router-dom";

export default function SuperAdminAuditPage() {
  return (
    <div className="p-6 max-w-2xl space-y-4">
      <h2 className="text-lg font-semibold">Platform audit</h2>
      <p className="text-sm text-chat-muted">
        Organization-scoped audit events (invitations, license changes, member actions) live under each organization.
        Open <strong>Organizations</strong>, select a tenant, then use the <strong>Audit log</strong> tab.
      </p>
      <p className="text-sm text-chat-muted">
        Platform-wide events such as organization deletion are recorded without tenant content and remain available after
        an organization is removed.
      </p>
      <Link to="/super-admin/organizations" className="aq-btn-secondary text-sm inline-block">
        Go to organizations
      </Link>
    </div>
  );
}
