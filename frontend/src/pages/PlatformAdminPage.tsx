import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  adminCreateOrganization,
  adminListMembers,
  adminListOrganizations,
  adminProvisionUser,
  adminUpdateOrganization,
  loadSession,
  type AdminMember,
  type AdminOrganization,
} from "../lib/api";

export default function PlatformAdminPage() {
  const [orgs, setOrgs] = useState<AdminOrganization[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>("");
  const [members, setMembers] = useState<AdminMember[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [invitePath, setInvitePath] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const session = loadSession();
  if (!session?.token) {
    return (
      <div className="p-8">
        <p>Not signed in.</p>
        <Link to="/login" className="text-chat-accent">
          Sign in
        </Link>
      </div>
    );
  }

  async function refreshOrgs() {
    const list = await adminListOrganizations(session);
    setOrgs(list);
    if (!selectedOrgId && list[0]) setSelectedOrgId(list[0].id);
  }

  async function refreshMembers(orgId: string) {
    if (!orgId) return;
    setMembers(await adminListMembers(session, orgId));
  }

  useEffect(() => {
    (async () => {
      try {
        await refreshOrgs();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load organizations");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (selectedOrgId) {
      refreshMembers(selectedOrgId).catch(() => setMembers([]));
    }
  }, [selectedOrgId]);

  async function onCreateOrg(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setInvitePath(null);
    const form = new FormData(e.currentTarget);
    try {
      await adminCreateOrganization(session, {
        name: String(form.get("name")),
        license_limit: Number(form.get("license_limit") ?? 0),
        license_status: String(form.get("license_status") || "test"),
      });
      (e.target as HTMLFormElement).reset();
      await refreshOrgs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create organization failed");
    }
  }

  async function onProvisionUser(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedOrgId) return;
    setError(null);
    setInvitePath(null);
    const form = new FormData(e.currentTarget);
    try {
      const result = await adminProvisionUser(session, selectedOrgId, {
        email: String(form.get("email")),
        full_name: String(form.get("full_name")),
        role: String(form.get("role") || "EDITOR"),
      });
      setInvitePath(result.invitation_setup_path);
      (e.target as HTMLFormElement).reset();
      await refreshMembers(selectedOrgId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Provision user failed");
    }
  }

  async function onUpdateLicense(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedOrgId) return;
    const form = new FormData(e.currentTarget);
    try {
      await adminUpdateOrganization(session, selectedOrgId, {
        license_limit: Number(form.get("license_limit")),
        license_status: String(form.get("license_status")),
      });
      await refreshOrgs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  const selectedOrg = orgs.find((o) => o.id === selectedOrgId);

  return (
    <div className="max-w-5xl mx-auto p-6 lg:p-10 space-y-8 font-sans">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Platform administration</h1>
          <p className="text-sm text-slate-600 mt-1">Provision client organizations, licenses, and user invitations.</p>
        </div>
        <Link to="/" className="text-sm text-chat-accent hover:underline">
          Back to app
        </Link>
      </div>

      {error ? <div className="aq-alert-error">{error}</div> : null}
      {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}

      <section className="aq-card aq-card-p space-y-4">
        <h2 className="font-medium">Create organization</h2>
        <form className="grid gap-3 md:grid-cols-3" onSubmit={onCreateOrg}>
          <input name="name" placeholder="Organization name" className="aq-input md:col-span-2" required />
          <input name="license_limit" type="number" min={0} defaultValue={0} className="aq-input" title="Licensed seats" />
          <select name="license_status" className="aq-input" defaultValue="test">
            <option value="test">test (dev test-mode org)</option>
            <option value="active">active</option>
            <option value="suspended">suspended</option>
          </select>
          <button type="submit" className="aq-btn-primary md:col-span-3 w-full md:w-auto">
            Create organization
          </button>
        </form>
        <p className="text-xs text-slate-500">
          New test orgs default to <strong>license_limit = 0</strong> with <strong>test</strong> status so they can sign in
          only when server test mode is enabled.
        </p>
      </section>

      <section className="aq-card aq-card-p space-y-4">
        <h2 className="font-medium">Organizations</h2>
        <select
          className="aq-input max-w-md"
          value={selectedOrgId}
          onChange={(e) => setSelectedOrgId(e.target.value)}
        >
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name} ({o.slug}) — seats {o.active_seats}/{o.license_limit} · {o.license_status}
            </option>
          ))}
        </select>

        {selectedOrg ? (
          <form className="grid gap-3 md:grid-cols-3 items-end" onSubmit={onUpdateLicense}>
            <label className="text-sm">
              License limit
              <input
                name="license_limit"
                type="number"
                min={0}
                defaultValue={selectedOrg.license_limit}
                className="aq-input mt-1"
              />
            </label>
            <label className="text-sm">
              Status
              <select name="license_status" defaultValue={selectedOrg.license_status} className="aq-input mt-1">
                <option value="test">test</option>
                <option value="active">active</option>
                <option value="suspended">suspended</option>
              </select>
            </label>
            <button type="submit" className="aq-btn-primary">
              Update license
            </button>
          </form>
        ) : null}
      </section>

      <section className="aq-card aq-card-p space-y-4">
        <h2 className="font-medium">Provision client user</h2>
        <form className="grid gap-3 md:grid-cols-2" onSubmit={onProvisionUser}>
          <input name="full_name" placeholder="Full name" className="aq-input" required />
          <input name="email" type="email" placeholder="Email" className="aq-input" required />
          <select name="role" className="aq-input" defaultValue="EDITOR">
            <option value="VIEWER">Viewer</option>
            <option value="REVIEWER">Reviewer</option>
            <option value="EDITOR">Editor</option>
            <option value="ORG_ADMIN">Org admin</option>
          </select>
          <button type="submit" className="aq-btn-primary" disabled={!selectedOrgId}>
            Generate invitation
          </button>
        </form>
        {invitePath ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
            <p className="font-medium text-amber-900">One-time setup link (copy now — not shown again)</p>
            <code className="block mt-2 break-all text-xs">{invitePath}</code>
          </div>
        ) : null}

        <h3 className="text-sm font-medium pt-2">Members</h3>
        <ul className="text-sm space-y-1">
          {members.map((m) => (
            <li key={m.id}>
              {m.full_name} &lt;{m.email}&gt; — {m.role}
              {!m.is_active || !m.user_is_active ? " (inactive)" : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
