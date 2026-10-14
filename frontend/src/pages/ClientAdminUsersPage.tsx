import { FormEvent, useEffect, useState } from "react";
import { InviteUrlSuccess } from "../components/admin/InviteUrlSuccess";
import { Combobox } from "../components/ui/dialog/Combobox";
import { Field } from "../components/ui/dialog/Field";
import { useAuth } from "../lib/authContext";
import { pickInviteUrl } from "../lib/inviteLinks";
import { fetchMembers, fetchOrgOverview, inviteMember, removeOrgMember } from "../lib/orgAdminApi";

const ROLE_OPTIONS = [
  { value: "ORG_ADMIN", label: "Organization admin" },
  { value: "EDITOR", label: "Editor" },
  { value: "VIEWER", label: "Viewer" },
];

export default function ClientAdminUsersPage() {
  const { session } = useAuth();
  const [members, setMembers] = useState<
    Array<{ membership_id: string; email: string; full_name: string; role: string; is_active: boolean }>
  >([]);
  const [seatsFull, setSeatsFull] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successUrl, setSuccessUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
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
    setSuccessUrl(null);
    setInviteBusy(true);
    const payload = {
      email: email.trim(),
      full_name: fullName.trim(),
      role,
    };
    try {
      const res = await inviteMember(session, payload);
      const url = pickInviteUrl(res);
      if (!url) {
        setError(
          "Invitation was created but no full URL was returned. Set PUBLIC_BASE_URL (PUBLIC_APP_URL) on the API server.",
        );
        return;
      }
      setSuccessUrl(url);
      setFullName("");
      setEmail("");
      setRole("EDITOR");
      try {
        await Promise.all([fetchMembers(session), fetchOrgOverview(session)]).then(([m, overview]) => {
          setMembers(m);
          setSeatsFull(overview.seats.is_full);
        });
      } catch {
        /* keep success visible even if table refresh fails */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invite failed");
    } finally {
      setInviteBusy(false);
    }
  }

  if (loading) return <p className="p-8 text-sm text-chat-muted">Loading users…</p>;

  return (
    <div className="max-w-3xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-semibold tracking-tight">Users & access</h1>
      <p className="text-sm text-chat-muted mt-2">
        Invite employees who can use the assistant. SSO connection is configured by your platform operator.
      </p>

      {seatsFull ? (
        <div className="admin-inline-alert border rounded-lg px-4 py-3 mt-4 text-sm" role="alert">
          All licensed seats are in use. Remove a member or ask your platform operator to increase your seat limit before
          inviting more people.
        </div>
      ) : null}

      <form className="admin-card p-6 mt-6 space-y-3" onSubmit={onInvite}>
        <h2 className="font-medium text-sm">Invite employee</h2>
        <div>
          <label htmlFor="inv-full-name" className="block text-sm font-medium mb-1">
            Full name
          </label>
          <input
            id="inv-full-name"
            name="full_name"
            required
            className="admin-input w-full"
            value={fullName}
            onChange={(ev) => setFullName(ev.target.value)}
            autoComplete="name"
          />
        </div>
        <div>
          <label htmlFor="inv-email" className="block text-sm font-medium mb-1">
            Work email
          </label>
          <input
            id="inv-email"
            name="email"
            type="email"
            required
            className="admin-input w-full"
            value={email}
            onChange={(ev) => setEmail(ev.target.value)}
            autoComplete="off"
          />
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
        {successUrl && !error ? <InviteUrlSuccess url={successUrl} /> : null}
        <button type="submit" className="admin-btn-primary" disabled={seatsFull || inviteBusy}>
          {inviteBusy ? "Sending…" : "Send invitation"}
        </button>
      </form>

      <div className="admin-card mt-8 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-chat-border text-chat-muted text-left">
              <th className="p-3">Name</th>
              <th className="p-3">Email</th>
              <th className="p-3">Role</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.membership_id} className="border-b border-chat-border last:border-0">
                <td className="p-3">{m.full_name}</td>
                <td className="p-3">{m.email}</td>
                <td className="p-3">{m.role.replace("_", " ")}</td>
                <td className="p-3">
                  <button
                    type="button"
                    className="text-xs text-red-700 underline"
                    onClick={async () => {
                      if (!session) return;
                      if (!window.confirm(`Remove ${m.full_name || m.email} from this organization?`)) return;
                      setError(null);
                      setSuccessUrl(null);
                      try {
                        await removeOrgMember(session, m.membership_id);
                        reload();
                      } catch (err) {
                        setError(err instanceof Error ? err.message : "Remove failed");
                      }
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
