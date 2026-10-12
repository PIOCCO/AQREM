import { Link } from "react-router-dom";

export default function ClientAdminUsersPage() {
  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-xl font-semibold">Users & access</h1>
      <p className="text-sm text-chat-muted mt-2">
        Invite employees and manage roles within your license limit. Organization admins can use review and
        questionnaire workflows from the main app navigation.
      </p>
      <p className="text-sm mt-4">
        For seat provisioning in hosted deployments, your platform operator may use the{" "}
        <Link to="/master-admin" className="text-[var(--chat-brand-mark)]">
          master console
        </Link>{" "}
        — client admins manage day-to-day access via invitations when enabled by your deployment.
      </p>
      <Link to="/settings" className="aq-btn-primary inline-block mt-6 text-sm">
        Organization settings
      </Link>
    </div>
  );
}
