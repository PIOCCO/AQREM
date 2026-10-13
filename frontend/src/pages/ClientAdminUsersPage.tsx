import { FormEvent, useEffect, useState } from "react";
import { Combobox } from "../components/ui/dialog/Combobox";
import { Field } from "../components/ui/dialog/Field";
import { useAuth } from "../lib/authContext";
import { fetchMembers, fetchOrgOverview, inviteMember } from "../lib/orgAdminApi";

const ROLE_OPTIONS = [
  { value: "ORG_ADMIN", label: "Organization admin" },
  { value: "EDITOR", label: "Editor" },
  { value: "VIEWER", label: "Viewer" },
];

export default function ClientAdminUsersPage() {
  const { session } = useAuth();
  const [members, setMembers] = useState<Array<{ email: string; full_name: string; role: string; is_active: boolean }>>([]);
  const [seatsFull, setSeatsFull] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [role, setRole] = useState("EDITOR");

  function reload() {
    if (!session) return;
    Promise.all([fetchMembers(session), fetchOrgOverview(session)])
      .then(([m, overview]) => {
        setMembers(m);
        setSeatsFull(overview.seats.is_full);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
  }, [session]);

  async function onInvite(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!session) return;
    setError(null);
    setSuccess(null);
    const form = new FormData(e.currentTarget);
    try {
      const res = await inviteMember(session, {
        email: String(form.get("email")),
        full_name: String(form.get("full_name")),
        role: String(form.get("role")),
      });
      setSuccess(`Invitation created. Share this link securely: ${res.invitation_setup_path}`);
      reload();
      e.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invite failed");
    }
  }

  if (loading) return <p className="p-8 text-sm text-chat-muted">Loading users…</p>;

  return (
    <div className="max-w-3xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-semibold tracking-tight">Users & access</h1>
      <p className="text-sm text-chat-muted mt-2">Invite employees who can use the assistant. SSO connection is configured by your platform operator.</p>

      {seatsFull ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mt-4 text-sm" role="alert">
          All licensed seats are in use. Remove a member or ask your platform operator to increase your seat limit before inviting more people.
        </div>
      ) : null}

      <form className="admin-card p-6 mt-6 space-y-3" onSubmit={onInvite}>
        <h2 className="font-medium text-sm">Invite employee</h2>
        <div>
          <label htmlFor="inv-full-name" className="block text-sm font-medium mb-1">
            Full name
          </label>
          <input id="inv-full-name" name="full_name" required className="admin-input w-full" />
        </div>
        <div>
          <label htmlFor="inv-email" className="block text-sm font-medium mb-1">
            Work email
          </label>
          <input id="inv-email" name="email" type="email" required className="admin-input w-full" />
        </div>
        <Field id="inv-role" label="Role">
          <input type="hidden" name="role" value={role} />
          <Combobox id="inv-role-ui" value={role} onChange={setRole} options={ROLE_OPTIONS} />
        </Field>
        {error ? (
          <div className="admin-inline-alert border rounded px-3 py-2 text-sm" role="alert">
            {error}
          </div>
        ) : null}
        {success ? (
          <div className="text-sm text-[var(--admin-status-active-text)] bg-[var(--admin-status-active-bg)] rounded px-3 py-2" role="status">
            {success}
          </div>
        ) : null}
        <button type="submit" className="aq-btn-primary" disabled={seatsFull}>
          Send invitation
        </button>
      </form>

      <div className="admin-card mt-8 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-chat-border text-chat-muted text-left">
              <th className="p-3">Name</th>
              <th className="p-3">Email</th>
              <th className="p-3">Role</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.email} className="border-b border-chat-border last:border-0">
                <td className="p-3">{m.full_name}</td>
                <td className="p-3">{m.email}</td>
                <td className="p-3">{m.role.replace("_", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
