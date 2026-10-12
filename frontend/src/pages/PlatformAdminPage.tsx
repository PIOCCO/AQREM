import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ToastProvider, useToast } from "../components/ui/Toast";
import { loadSession } from "../lib/api";
import {
  ASSIGNABLE_ROLES,
  licenseStatusLabel,
  roleLabel,
} from "../lib/roleLabels";
import {
  createAdminOrganization,
  deactivateMember,
  fetchAdminContext,
  fetchAdminOrganizations,
  fetchOrgAudit,
  fetchOrgInvitations,
  fetchOrganizationDirectory,
  inviteOrganizationUser,
  isAdminApiError,
  resendInvitation,
  revokeInvitation,
  updateAdminOrganization,
  updateMemberRole,
  type AdminOrganization,
  type DirectoryRow,
} from "../lib/platformAdminApi";

type TabId = "overview" | "members" | "license" | "invitations" | "audit";

function statusBadgeClass(status: string) {
  if (status === "active") return "admin-badge-active";
  if (status === "test") return "admin-badge-test";
  return "admin-badge-suspended";
}

function SeatBar({ used, limit, suspended }: { used: number; limit: number; suspended?: boolean }) {
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const full = limit > 0 && used >= limit;
  const barColor = suspended
    ? "var(--admin-seat-muted)"
    : full
      ? "var(--admin-seat-full)"
      : "var(--admin-seat-ok)";
  return (
    <div className="h-1.5 w-full rounded-full bg-chat-surface-subtle overflow-hidden" aria-hidden>
      <div className="h-full transition-all" style={{ width: `${pct}%`, background: barColor }} />
    </div>
  );
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function PlatformAdminInner() {
  const toast = useToast();
  const session = loadSession();
  const [context, setContext] = useState<{ test_mode_effective: boolean } | null>(null);
  const [orgs, setOrgs] = useState<AdminOrganization[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string>("");
  const [tab, setTab] = useState<TabId>("members");
  const [loading, setLoading] = useState(true);
  const [showNewOrg, setShowNewOrg] = useState(false);
  const [directory, setDirectory] = useState<DirectoryRow[]>([]);
  const [dirPage, setDirPage] = useState(1);
  const [dirTotal, setDirTotal] = useState(0);
  const [dirSeats, setDirSeats] = useState<AdminOrganization["seats"] | null>(null);
  const [dirLoading, setDirLoading] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [invitations, setInvitations] = useState<
    { id: string; email: string; role: string; expires_at: string }[]
  >([]);
  const [audit, setAudit] = useState<
    { id: string; created_at: string; actor_email: string; action: string; target: string }[]
  >([]);
  const [lastInvite, setLastInvite] = useState<{ path: string; expires: string } | null>(null);

  const selected = useMemo(() => orgs.find((o) => o.id === selectedId), [orgs, selectedId]);

  const refreshOrgs = useCallback(async () => {
    if (!session?.token) return;
    const data = await fetchAdminOrganizations(session, { q: search || undefined, status: filter });
    setOrgs(data.items);
    setCounts(data.counts);
    if (!selectedId && data.items[0]) setSelectedId(data.items[0].id);
  }, [session, search, filter, selectedId]);

  const refreshDirectory = useCallback(async () => {
    if (!session?.token || !selectedId) return;
    setDirLoading(true);
    try {
      const data = await fetchOrganizationDirectory(session, selectedId, dirPage, 5);
      setDirectory(data.rows);
      setDirTotal(data.total);
      setDirSeats(data.seats);
    } finally {
      setDirLoading(false);
    }
  }, [session, selectedId, dirPage]);

  useEffect(() => {
    if (!session?.token) return;
    (async () => {
      try {
        const ctx = await fetchAdminContext(session);
        setContext(ctx);
        await refreshOrgs();
      } catch {
        toast.push("Failed to load platform administration", "err");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    refreshOrgs().catch(() => undefined);
  }, [search, filter]);

  useEffect(() => {
    setDirPage(1);
    setInviteError(null);
    setLastInvite(null);
  }, [selectedId]);

  useEffect(() => {
    if (tab === "members" || tab === "overview") refreshDirectory().catch(() => undefined);
    if (tab === "invitations" && session?.token && selectedId) {
      fetchOrgInvitations(session, selectedId).then(setInvitations).catch(() => setInvitations([]));
    }
    if (tab === "audit" && session?.token && selectedId) {
      fetchOrgAudit(session, selectedId)
        .then((d) => setAudit(d.items))
        .catch(() => setAudit([]));
    }
  }, [tab, selectedId, dirPage, refreshDirectory, session]);

  if (!session?.token) {
    return (
      <div className="p-8">
        <Link to="/login?next=%2Fplatform-admin">Sign in</Link>
      </div>
    );
  }
  const auth = session;

  async function onCreateOrg(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const created = await createAdminOrganization(auth, {
        name: String(form.get("name")),
        license_limit: Number(form.get("license_limit")),
        environment: String(form.get("environment")),
        owner_display_name: String(form.get("owner") || "") || undefined,
      });
      setShowNewOrg(false);
      toast.push(`Organization “${created.name}” created`, "ok");
      await refreshOrgs();
      setSelectedId(created.id);
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Create failed", "err");
    }
  }

  async function onInvite(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedId || !selected) return;
    setInviteError(null);
    const form = new FormData(e.currentTarget);
    try {
      const result = await inviteOrganizationUser(auth, selectedId, {
        full_name: String(form.get("full_name")),
        email: String(form.get("email")),
        role: String(form.get("role")),
      });
      setLastInvite({ path: result.invitation_setup_path, expires: result.invitation_expires_at });
      toast.push("Invitation sent", "ok");
      (e.target as HTMLFormElement).reset();
      await refreshOrgs();
      await refreshDirectory();
    } catch (err) {
      if (isAdminApiError(err) && err.admin.code === "SEATS_FULL") {
        setInviteError(
          `No seats left (${selected.seats.seats_used} of ${selected.seats.seats_limit} used). Increase the seat limit or remove a member.`,
        );
      } else {
        setInviteError(err instanceof Error ? err.message : "Invite failed");
      }
    }
  }

  const filters = [
    { id: "all", label: "All", count: counts.all ?? 0 },
    { id: "active", label: "Active", count: counts.active ?? 0 },
    { id: "suspended", label: "Suspended", count: counts.suspended ?? 0 },
    { id: "test", label: "Test", count: counts.test ?? 0 },
  ];

  const seatsFull = selected?.seats.is_full ?? false;
  const dirPages = Math.max(1, Math.ceil(dirTotal / 5));

  return (
    <div className="admin-shell font-sans text-chat-fg">
      <header className="border-b border-chat-border bg-chat-surface px-6 py-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Platform administration</h1>
          <p className="text-sm text-chat-muted mt-1">
            Provision client organizations, licenses, and user invitations.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/" className="text-sm text-chat-muted hover:text-chat-fg">
            Back to app
          </Link>
          <button type="button" className="aq-btn-primary text-sm" onClick={() => setShowNewOrg(true)}>
            + New organization
          </button>
        </div>
      </header>

      <div className="flex flex-col lg:flex-row min-h-[calc(100vh-5rem)]">
        <aside
          className="w-full lg:w-[var(--admin-sidebar-width)] shrink-0 border-b lg:border-b-0 lg:border-r border-chat-border bg-chat-surface p-4 space-y-4"
          aria-label="Organizations"
        >
          <label className="block text-xs font-medium text-chat-muted" htmlFor="org-search">
            Search organizations
          </label>
          <input
            id="org-search"
            className="admin-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name"
          />
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
            {filters.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`rounded-full px-3 py-1 text-xs font-medium border ${
                  filter === f.id ? "bg-chat-accent text-white border-chat-accent" : "border-chat-border text-chat-muted"
                }`}
                onClick={() => setFilter(f.id)}
              >
                {f.label} {f.count}
              </button>
            ))}
          </div>
          {loading ? (
            <p className="text-sm text-chat-muted">Loading organizations…</p>
          ) : orgs.length === 0 ? (
            <p className="text-sm text-chat-muted">No organizations match your filters.</p>
          ) : (
            <ul className="space-y-2 max-h-[60vh] overflow-y-auto">
              {orgs.map((o) => (
                <li key={o.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(o.id)}
                    className={`w-full text-left admin-card p-3 transition-colors ${
                      selectedId === o.id ? "ring-2 ring-chat-brand-mark/40 bg-chat-surface-subtle" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-sm truncate">{o.name}</span>
                      <span className={`text-[10px] uppercase px-2 py-0.5 rounded-full ${statusBadgeClass(o.license_status)}`}>
                        {licenseStatusLabel(o.license_status)}
                      </span>
                    </div>
                    <p className="text-xs text-chat-muted mt-1 capitalize">{o.environment}</p>
                    <p className="text-xs mt-2">
                      {o.seats.seats_used} / {o.seats.seats_limit} seats
                    </p>
                    <SeatBar
                      used={o.seats.seats_used}
                      limit={o.seats.seats_limit}
                      suspended={o.license_status === "suspended" || o.license_status === "expired"}
                    />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="flex-1 p-4 lg:p-6 min-w-0">
          {!selected ? (
            <p className="text-chat-muted text-sm">Select an organization to manage.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-lg font-semibold">{selected.name}</h2>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadgeClass(selected.license_status)}`}>
                      {licenseStatusLabel(selected.license_status)}
                    </span>
                  </div>
                  <p className="text-xs text-chat-muted mt-1 capitalize">
                    {selected.environment} · Created {formatDate(selected.created_at)}
                    {selected.owner_display_name ? ` · Owner: ${selected.owner_display_name}` : ""}
                  </p>
                </div>
              </div>

              <nav className="flex flex-wrap gap-4 border-b border-chat-border mb-6" aria-label="Organization sections">
                {(
                  [
                    ["overview", "Overview"],
                    ["members", `Members ${selected.seats.active_members}`],
                    ["license", "License"],
                    ["invitations", `Invitations ${selected.seats.pending_invitations}`],
                    ["audit", "Audit log"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={`pb-2 text-sm font-medium border-b-2 -mb-px ${
                      tab === id ? "border-chat-accent text-chat-fg" : "border-transparent text-chat-muted"
                    }`}
                    onClick={() => setTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </nav>

              {tab === "members" && (
                <div className="space-y-6">
                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="admin-card p-4">
                      <p className="text-xs text-chat-muted">Seats used</p>
                      <p className="text-2xl font-semibold mt-1">
                        {selected.seats.seats_used}{" "}
                        <span className="text-base font-normal text-chat-muted">of {selected.seats.seats_limit}</span>
                      </p>
                      <SeatBar used={selected.seats.seats_used} limit={selected.seats.seats_limit} />
                      <p className="text-xs text-chat-muted mt-2">
                        {selected.seats.active_members} active members + {selected.seats.pending_invitations} pending
                        invitations. Pending invitations count toward seats.
                      </p>
                      <button type="button" className="text-xs text-[var(--admin-seat-ok)] mt-2" onClick={() => setTab("license")}>
                        Manage license
                      </button>
                    </div>
                    <div className="admin-card p-4">
                      <p className="text-xs text-chat-muted">License status</p>
                      <p className="text-2xl font-semibold mt-1">{licenseStatusLabel(selected.license_status)}</p>
                      <p className="text-xs text-chat-muted mt-2">
                        {selected.license_renews_at ? `Renews ${formatDate(selected.license_renews_at)}` : "—"}
                      </p>
                    </div>
                  </div>

                  <div className="admin-card p-4 space-y-4">
                    <h3 className="font-medium text-sm">Invite a member</h3>
                    {inviteError ? (
                      <div className="admin-inline-alert border rounded-lg px-3 py-2 text-sm flex flex-wrap gap-2 justify-between" role="alert">
                        <span>{inviteError}</span>
                        {inviteError.includes("No seats left") ? (
                          <button type="button" className="underline font-medium" onClick={() => setTab("license")}>
                            Increase seat limit
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                    <form className="grid md:grid-cols-3 gap-4" onSubmit={onInvite}>
                      <div>
                        <label htmlFor="inv-name" className="text-xs font-medium">
                          Full name
                        </label>
                        <input id="inv-name" name="full_name" className="admin-input mt-1" required />
                      </div>
                      <div>
                        <label htmlFor="inv-email" className="text-xs font-medium">
                          Work email
                        </label>
                        <input id="inv-email" name="email" type="email" className="admin-input mt-1" required />
                      </div>
                      <div>
                        <label htmlFor="inv-role" className="text-xs font-medium">
                          Role
                        </label>
                        <select id="inv-role" name="role" className="admin-input mt-1" defaultValue="EDITOR">
                          {ASSIGNABLE_ROLES.map((r) => (
                            <option key={r} value={r}>
                              {roleLabel(r)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button type="submit" className="aq-btn-primary md:col-span-3 w-fit" disabled={seatsFull}>
                        Send invitation
                      </button>
                    </form>
                    {lastInvite ? (
                      <div className="text-sm border border-chat-border rounded-lg p-3 space-y-2">
                        <p className="font-medium">Invitation link (expires {formatDate(lastInvite.expires)})</p>
                        <code className="block text-xs break-all">{lastInvite.path}</code>
                        <button
                          type="button"
                          className="text-xs aq-btn-primary"
                          onClick={() => navigator.clipboard.writeText(window.location.origin + lastInvite.path)}
                        >
                          Copy link
                        </button>
                      </div>
                    ) : null}
                  </div>

                  <div className="admin-card overflow-hidden">
                    {dirLoading ? (
                      <p className="p-4 text-sm text-chat-muted">Loading members…</p>
                    ) : directory.length === 0 ? (
                      <p className="p-4 text-sm text-chat-muted">No members or pending invitations yet.</p>
                    ) : (
                      <table className="w-full text-sm">
                        <thead className="bg-chat-surface-subtle text-left text-xs text-chat-muted">
                          <tr>
                            <th className="p-3">Name</th>
                            <th className="p-3">Email</th>
                            <th className="p-3">Role</th>
                            <th className="p-3">Status</th>
                            <th className="p-3">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {directory.map((row) => (
                            <tr key={row.row_id} className="border-t border-chat-border">
                              <td className="p-3">{row.full_name}</td>
                              <td className="p-3">{row.email}</td>
                              <td className="p-3">
                                {row.kind === "member" && row.membership_id ? (
                                  <select
                                    className="admin-input py-1"
                                    value={row.role}
                                    aria-label={`Role for ${row.email}`}
                                    onChange={(e) =>
                                      updateMemberRole(auth, selectedId, row.membership_id!, e.target.value).then(
                                        () => refreshDirectory(),
                                      )
                                    }
                                  >
                                    {ASSIGNABLE_ROLES.map((r) => (
                                      <option key={r} value={r}>
                                        {roleLabel(r)}
                                      </option>
                                    ))}
                                  </select>
                                ) : (
                                  roleLabel(row.role)
                                )}
                              </td>
                              <td className="p-3">{row.status}</td>
                              <td className="p-3 space-x-2">
                                {row.kind === "invitation" && row.invitation_id ? (
                                  <>
                                    <button
                                      type="button"
                                      className="text-xs underline"
                                      onClick={() =>
                                        resendInvitation(auth, selectedId, row.invitation_id!).then(() =>
                                          toast.push("Invitation resent", "ok"),
                                        )
                                      }
                                    >
                                      Resend
                                    </button>
                                    <button
                                      type="button"
                                      className="text-xs underline text-red-700"
                                      onClick={() =>
                                        revokeInvitation(auth, selectedId, row.invitation_id!).then(() =>
                                          refreshDirectory(),
                                        )
                                      }
                                    >
                                      Revoke
                                    </button>
                                  </>
                                ) : row.membership_id ? (
                                  <button
                                    type="button"
                                    className="text-xs underline text-red-700"
                                    onClick={() =>
                                      deactivateMember(auth, selectedId, row.membership_id!).then(() => {
                                        refreshOrgs();
                                        refreshDirectory();
                                      })
                                    }
                                  >
                                    Remove
                                  </button>
                                ) : null}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    {dirPages > 1 ? (
                      <div className="flex justify-end gap-2 p-3 border-t border-chat-border">
                        <button
                          type="button"
                          className="text-xs px-2 py-1 border rounded"
                          disabled={dirPage <= 1}
                          onClick={() => setDirPage((p) => p - 1)}
                        >
                          Previous
                        </button>
                        <span className="text-xs text-chat-muted self-center">
                          Page {dirPage} of {dirPages}
                        </span>
                        <button
                          type="button"
                          className="text-xs px-2 py-1 border rounded"
                          disabled={dirPage >= dirPages}
                          onClick={() => setDirPage((p) => p + 1)}
                        >
                          Next
                        </button>
                      </div>
                    ) : null}
                  </div>
                </div>
              )}

              {tab === "license" && selected && (
                <LicenseTab org={selected} session={auth} onSaved={refreshOrgs} />
              )}

              {tab === "invitations" && (
                <div className="admin-card p-4 space-y-3">
                  {invitations.length === 0 ? (
                    <p className="text-sm text-chat-muted">No pending invitations.</p>
                  ) : (
                    invitations.map((inv) => (
                      <div key={inv.id} className="flex flex-wrap justify-between gap-2 border-b border-chat-border pb-2">
                        <div>
                          <p className="text-sm font-medium">{inv.email}</p>
                          <p className="text-xs text-chat-muted">
                            {roleLabel(inv.role)} · Expires {formatDate(inv.expires_at)}
                          </p>
                        </div>
                        <div className="space-x-2">
                          <button
                            type="button"
                            className="text-xs underline"
                            onClick={() =>
                              resendInvitation(auth, selectedId, inv.id).then((r) => {
                                setLastInvite({ path: r.invitation_setup_path, expires: r.invitation_expires_at });
                                toast.push("Invitation resent", "ok");
                              })
                            }
                          >
                            Resend
                          </button>
                          <button
                            type="button"
                            className="text-xs underline"
                            onClick={() =>
                              revokeInvitation(auth, selectedId, inv.id).then(() =>
                                fetchOrgInvitations(auth, selectedId).then(setInvitations),
                              )
                            }
                          >
                            Revoke
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {tab === "audit" && (
                <div className="admin-card overflow-hidden">
                  {audit.length === 0 ? (
                    <p className="p-4 text-sm text-chat-muted">No audit events yet.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="bg-chat-surface-subtle text-xs text-chat-muted text-left">
                        <tr>
                          <th className="p-3">Time</th>
                          <th className="p-3">Actor</th>
                          <th className="p-3">Action</th>
                          <th className="p-3">Target</th>
                        </tr>
                      </thead>
                      <tbody>
                        {audit.map((a) => (
                          <tr key={a.id} className="border-t border-chat-border">
                            <td className="p-3 whitespace-nowrap">{formatDate(a.created_at)}</td>
                            <td className="p-3">{a.actor_email ?? "—"}</td>
                            <td className="p-3 capitalize">{a.action}</td>
                            <td className="p-3">{a.target}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {tab === "overview" && (
                <div className="admin-card p-4 text-sm space-y-2">
                  <p>
                    <strong>Seats:</strong> {selected.seats.seats_used} / {selected.seats.seats_limit} used
                  </p>
                  <p>
                    <strong>Slug:</strong> {selected.slug}
                  </p>
                  <p className="text-chat-muted">Use the Members tab to invite users or the License tab to adjust seats.</p>
                </div>
              )}
            </>
          )}
        </main>
      </div>

      {showNewOrg ? (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true">
          <div className="admin-card max-w-md w-full p-6 space-y-4">
            <h2 className="text-lg font-semibold">New organization</h2>
            <form className="space-y-3" onSubmit={onCreateOrg}>
              <div>
                <label htmlFor="new-name" className="text-xs font-medium">
                  Organization name
                </label>
                <input id="new-name" name="name" className="admin-input mt-1" required />
              </div>
              <div>
                <label htmlFor="new-seats" className="text-xs font-medium">
                  Seat limit
                </label>
                <input id="new-seats" name="license_limit" type="number" min={1} defaultValue={10} className="admin-input mt-1" required />
              </div>
              {context?.test_mode_effective ? (
                <div>
                  <label htmlFor="new-env" className="text-xs font-medium">
                    Environment
                  </label>
                  <select id="new-env" name="environment" className="admin-input mt-1" defaultValue="production">
                    <option value="production">Production</option>
                    <option value="test">Test</option>
                  </select>
                </div>
              ) : (
                <input type="hidden" name="environment" value="production" />
              )}
              <div>
                <label htmlFor="new-owner" className="text-xs font-medium">
                  Owner (optional)
                </label>
                <input id="new-owner" name="owner" className="admin-input mt-1" />
              </div>
              <div className="flex gap-2 justify-end pt-2">
                <button type="button" className="text-sm px-3 py-2" onClick={() => setShowNewOrg(false)}>
                  Cancel
                </button>
                <button type="submit" className="aq-btn-primary text-sm">
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LicenseTab({
  org,
  session,
  onSaved,
}: {
  org: AdminOrganization;
  session: NonNullable<ReturnType<typeof loadSession>>;
  onSaved: () => Promise<void>;
}) {
  const toast = useToast();
  const [limit, setLimit] = useState(org.license_limit);
  const [status, setStatus] = useState(org.license_status);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLimit(org.license_limit);
    setStatus(org.license_status);
    setDirty(false);
  }, [org.id, org.license_limit, org.license_status]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (status === "suspended" && !window.confirm("Suspend this organization? Members will lose access.")) return;
    if (limit < org.seats.seats_used) {
      setError(`Limit cannot be below ${org.seats.seats_used} seats in use.`);
      return;
    }
    try {
      await updateAdminOrganization(session, org.id, { license_limit: limit, license_status: status });
      toast.push("License updated", "ok");
      setDirty(false);
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  return (
    <form className="admin-card p-4 max-w-lg space-y-4" onSubmit={save}>
      {dirty ? <p className="text-xs text-amber-700">Unsaved changes</p> : null}
      {error ? (
        <div className="text-sm admin-inline-alert border rounded px-3 py-2" role="alert">
          {error}
        </div>
      ) : null}
      <div>
        <label htmlFor="lic-limit" className="text-xs font-medium">
          Seat limit
        </label>
        <input
          id="lic-limit"
          type="number"
          min={org.seats.seats_used}
          className="admin-input mt-1"
          value={limit}
          onChange={(e) => {
            setLimit(Number(e.target.value));
            setDirty(true);
          }}
        />
      </div>
      <div>
        <label htmlFor="lic-status" className="text-xs font-medium">
          Status
        </label>
        <select
          id="lic-status"
          className="admin-input mt-1"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setDirty(true);
          }}
        >
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="expired">Expired</option>
          {org.license_status === "test" ? <option value="test">Test</option> : null}
        </select>
      </div>
      <button type="submit" className="aq-btn-primary text-sm" disabled={!dirty}>
        Save changes
      </button>
    </form>
  );
}

export default function PlatformAdminPage() {
  return (
    <ToastProvider>
      <PlatformAdminInner />
    </ToastProvider>
  );
}
