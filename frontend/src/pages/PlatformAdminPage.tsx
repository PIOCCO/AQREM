import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LogoHomeLink } from "../components/brand/LogoHomeLink";
import { ToastProvider, useToast } from "../components/ui/Toast";
import { loadSession } from "../lib/api";
import { resolveApiBase } from "../lib/apiBase";
import {
  licenseStatusLabel,
  platformRoleLabel,
  roleLabel,
} from "../lib/roleLabels";
import { InvitePlatformStaffDialog } from "../components/platform-admin/InvitePlatformStaffDialog";
import { LicenseSummaryCard } from "../components/platform-admin/LicenseSummaryCard";
import { RemoveMemberDialog } from "../components/platform-admin/RemoveMemberDialog";
import { DeleteOrganizationDialog } from "../components/platform-admin/DeleteOrganizationDialog";
import { OrgInvitationsPanel } from "../components/platform-admin/OrgInvitationsPanel";
import {
  createAdminOrganization,
  deleteAdminOrganization,
  restoreAdminOrganization,
  deactivateMember,
  fetchAdminContext,
  fetchAdminOrganizations,
  fetchOrgAudit,
  fetchOrgInvitations,
  fetchOrganizationDirectory,
  fetchInvitationsSetup,
  fetchPermissionsMatrix,
  fetchPlatformStaff,
  inviteOrganizationUser,
  invitePlatformStaff,
  isAdminApiError,
  resendInvitation,
  revokeInvitation,
  updateAdminOrganization,
  type AdminOrganization,
  type DirectoryRow,
  type PermissionsMatrix,
  type PlatformStaffMember,
} from "../lib/platformAdminApi";

type ConsoleSection = "organizations" | "team" | "roles";
type TabId = "overview" | "members" | "license" | "invitations" | "audit";

type PlatformAdminPageProps = {
  /** Render inside SuperAdminShell (no duplicate header / section tabs). */
  embedded?: boolean;
  surface?: "organizations" | "settings";
  defaultOrgTab?: TabId;
};

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

function shortOrgId(id: string) {
  return id.length >= 8 ? id.slice(0, 8) : id;
}

function MembersTableSkeleton() {
  return (
    <div className="p-4 space-y-3" aria-busy="true" aria-label="Loading members">
      <div className="admin-skeleton-line w-1/3" />
      <div className="admin-skeleton-line w-full" />
      <div className="admin-skeleton-line w-full" />
      <div className="admin-skeleton-line w-2/3" />
    </div>
  );
}

function PlatformAdminInner({
  embedded = false,
  surface = "organizations",
  defaultOrgTab = "members",
}: PlatformAdminPageProps) {
  const toast = useToast();
  const session = loadSession();
  const sessionToken = session?.token ?? null;
  const [context, setContext] = useState<import("../lib/platformAdminApi").AdminContext | null>(null);
  const [orgs, setOrgs] = useState<AdminOrganization[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string>("");
  const [tab, setTab] = useState<TabId>(defaultOrgTab);
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
  const [lastInvite, setLastInvite] = useState<{ url: string; expires: string } | null>(null);
  const [consoleSection, setConsoleSection] = useState<ConsoleSection>(
    surface === "settings" ? "team" : "organizations",
  );
  const [platformStaff, setPlatformStaff] = useState<PlatformStaffMember[]>([]);
  const [permMatrix, setPermMatrix] = useState<PermissionsMatrix | null>(null);
  const [teamLoading, setTeamLoading] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<{ membershipId: string; name: string } | null>(null);
  const [removeLoading, setRemoveLoading] = useState(false);
  const [staffInviteOpen, setStaffInviteOpen] = useState(false);
  const [staffInviteRole, setStaffInviteRole] = useState<"SUPER_ADMIN" | "PLATFORM_SUPPORT" | "PLATFORM_BILLING">(
    "PLATFORM_SUPPORT",
  );
  const [staffInviteLoading, setStaffInviteLoading] = useState(false);
  const [deleteOrgOpen, setDeleteOrgOpen] = useState(false);
  const [deleteOrgLoading, setDeleteOrgLoading] = useState(false);
  const [deleteOrgError, setDeleteOrgError] = useState<string | null>(null);
  const [inviteSetup, setInviteSetup] = useState<Awaited<ReturnType<typeof fetchInvitationsSetup>> | null>(null);

  const selected = useMemo(
    () => (Array.isArray(orgs) ? orgs : []).find((o) => o.id === selectedId),
    [orgs, selectedId],
  );

  const refreshOrgs = useCallback(async () => {
    const s = loadSession();
    if (!s?.token) return;
    const data = await fetchAdminOrganizations(s, { q: search || undefined, status: filter });
    setOrgs(Array.isArray(data.items) ? data.items : []);
    setCounts(data.counts ?? { all: 0, active: 0, suspended: 0, test: 0 });
    if (!selectedId && data.items[0]) setSelectedId(data.items[0].id);
  }, [search, filter, selectedId]);

  const refreshDirectory = useCallback(async () => {
    const s = loadSession();
    if (!s?.token || !selectedId) return;
    setDirLoading(true);
    try {
      const data = await fetchOrganizationDirectory(s, selectedId, dirPage, 5, selected ?? undefined);
      setDirectory(data.rows);
      setDirTotal(data.total);
      setDirSeats(data.seats);
    } catch {
      setDirectory([]);
      toast.push("Failed to load members", "err");
    } finally {
      setDirLoading(false);
    }
  }, [selectedId, dirPage, selected]);

  useEffect(() => {
    if (!sessionToken) return;
    (async () => {
      const s = loadSession();
      if (!s?.token) return;
      try {
        const ctx = await fetchAdminContext(s);
        setContext(ctx);
        await refreshOrgs();
      } catch {
        toast.push("Failed to load platform administration", "err");
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionToken]);

  useEffect(() => {
    if (!sessionToken || consoleSection !== "team") return;
    setTeamLoading(true);
    fetchPlatformStaff(loadSession()!)
      .then(setPlatformStaff)
      .catch(() => toast.push("Failed to load platform team", "err"))
      .finally(() => setTeamLoading(false));
  }, [consoleSection, sessionToken]);

  useEffect(() => {
    const wantMatrix = consoleSection === "roles" || (embedded && surface === "settings");
    if (!sessionToken || !wantMatrix) return;
    fetchPermissionsMatrix(loadSession()!)
      .then(setPermMatrix)
      .catch(() => toast.push("Failed to load roles matrix", "err"));
  }, [consoleSection, sessionToken, embedded, surface]);

  useEffect(() => {
    refreshOrgs().catch(() => undefined);
  }, [search, filter]);

  useEffect(() => {
    setTab(defaultOrgTab);
  }, [defaultOrgTab]);

  useEffect(() => {
    setConsoleSection(surface === "settings" ? "team" : "organizations");
  }, [surface]);

  useEffect(() => {
    setDirPage(1);
    setInviteError(null);
    setLastInvite(null);
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId || !sessionToken) {
      setInviteSetup(null);
      return;
    }
    if (tab === "members" || tab === "overview" || tab === "invitations") {
      fetchInvitationsSetup(loadSession()!, selectedId)
        .then(setInviteSetup)
        .catch(() => setInviteSetup(null));
    }
  }, [tab, selectedId, sessionToken]);

  const invitationsTabCount = useMemo(() => {
    const fromSeats = selected?.seats.pending_invitations ?? 0;
    if (inviteSetup?.pending_org_admin_invite) {
      return Math.max(fromSeats, 1);
    }
    return fromSeats;
  }, [selected?.seats.pending_invitations, inviteSetup?.pending_org_admin_invite]);

  const adminSetupLabel = useMemo(() => {
    if (!inviteSetup) return selected && selected.seats.pending_invitations > 0 ? "Pending" : "Set up";
    if (inviteSetup.has_active_org_admin || inviteSetup.admin_accepted) return "Complete";
    if (inviteSetup.pending_org_admin_invite) return "Pending";
    if (inviteSetup.admin_invitation_status === "expired" || inviteSetup.admin_invitation_status === "revoked") {
      return "Needs attention";
    }
    return "Set up";
  }, [inviteSetup, selected]);

  useEffect(() => {
    if (tab === "members" || tab === "overview") refreshDirectory().catch(() => undefined);
    if (tab === "invitations" && sessionToken && selectedId) {
      fetchOrgInvitations(loadSession()!, selectedId).then(setInvitations).catch(() => setInvitations([]));
    }
    if (tab === "audit" && sessionToken && selectedId) {
      fetchOrgAudit(loadSession()!, selectedId)
        .then((d) => setAudit(d.items))
        .catch(() => setAudit([]));
    }
  }, [tab, selectedId, dirPage, refreshDirectory, sessionToken]);

  if (!session?.token) {
    return (
      <div className="p-8">
        <Link to="/login?next=%2Fsuper-admin">Sign in</Link>
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
      setLastInvite({
        url: result.invitation_setup_url,
        expires: result.invitation_expires_at,
      });
      toast.push("Invitation sent", "ok");
      (e.target as HTMLFormElement).reset();
      await refreshOrgs();
      await refreshDirectory();
    } catch (err) {
      if (isAdminApiError(err) && err.admin.code === "SEATS_FULL") {
        setInviteError(
          `No seats left (${selected.seats.seats_used} of ${selected.seats.seats_limit} used). Increase the seat limit or remove a member.`,
        );
      } else if (isAdminApiError(err) && err.admin.code === "NO_LICENSED_SEATS") {
        setInviteError(err.admin.message);
      } else {
        setInviteError(err instanceof Error ? err.message : "Invite failed");
      }
    }
  }

  const filters = [
    { id: "all", label: "All", count: counts.all ?? 0 },
    { id: "active", label: "Active", count: counts.active ?? 0 },
    { id: "suspended", label: "Suspended", count: counts.suspended ?? 0 },
    { id: "expired", label: "Expired", count: counts.expired ?? 0 },
    { id: "test", label: "Test", count: counts.test ?? 0 },
    { id: "pending_deletion", label: "Pending deletion", count: counts.pending_deletion ?? 0 },
  ];

  const membersTabCount =
    tab === "members" && !dirLoading ? dirTotal : (selected?.seats.active_members ?? 0) + (selected?.seats.pending_invitations ?? 0);

  const licenseBlocksInvite =
    selected?.license_status === "expired" || selected?.license_status === "suspended" || selected?.is_active === false;
  const showInviteAdminForm =
    !licenseBlocksInvite && !inviteSetup?.has_active_org_admin && !inviteSetup?.pending_org_admin_invite;

  const seatsFull = selected?.seats?.is_full ?? false;
  const dirPages = Math.max(1, Math.ceil(dirTotal / 5));

  return (
    <div className={embedded ? "font-sans text-chat-fg" : "admin-shell font-sans text-chat-fg"}>
      {!embedded ? (
        <header className="border-b border-chat-border bg-chat-surface px-6 py-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <LogoHomeLink variant="full" className="mb-2" />
            <h1 className="text-xl font-semibold tracking-tight">Super Admin</h1>
            <p className="text-sm text-chat-muted mt-1">
              Platform operations only — organizations, licenses, and invitations. No customer workspace data.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <nav className="flex gap-2 text-sm" aria-label="Platform console">
              {(
                [
                  ["organizations", "Organizations"],
                  ["team", "Team & roles"],
                  ["roles", "Roles"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`rounded-lg px-3 py-1.5 border ${
                    consoleSection === id ? "border-chat-accent bg-chat-surface-subtle" : "border-chat-border text-chat-muted"
                  }`}
                  onClick={() => setConsoleSection(id)}
                >
                  {label}
                </button>
              ))}
            </nav>
            {consoleSection === "organizations" ? (
              <button type="button" className="aq-btn-primary text-sm" onClick={() => setShowNewOrg(true)}>
                + New organization
              </button>
            ) : null}
          </div>
        </header>
      ) : null}

      {embedded && surface === "organizations" ? (
        <div className="px-4 pt-4 flex justify-end">
          <button type="button" className="aq-btn-primary text-sm" onClick={() => setShowNewOrg(true)}>
            + New organization
          </button>
        </div>
      ) : null}

      {context?.organization_soft_delete !== true && (embedded || consoleSection === "organizations") ? (
        <div className="mx-6 mt-4 admin-inline-alert admin-inline-alert-danger" role="alert">
          <strong className="font-medium">Organization delete unavailable.</strong> The API at{" "}
          {resolveApiBase() || "port 8000"} does not report soft-delete support. Restart the backend from the latest
          AQREM code on port 8000 (POST /api/v1/admin/organizations/…/delete). The Vite UI on :5173 alone
          cannot schedule deletion.
        </div>
      ) : null}

      {context?.super_admin_warning && (embedded || consoleSection === "organizations") ? (
        <div className="mx-6 mt-4 admin-inline-alert flex flex-wrap items-center justify-between gap-3" role="alert">
          <span>
            <strong className="font-medium">Warning:</strong> Fewer than two active super admins. Add another super
            admin before production cutover.
          </span>
          <button
            type="button"
            className="aq-btn-secondary text-xs py-1.5 h-auto"
            onClick={() => {
              setStaffInviteRole("SUPER_ADMIN");
              setConsoleSection("team");
              setStaffInviteOpen(true);
            }}
          >
            Add super admin
          </button>
        </div>
      ) : null}

      {(consoleSection === "team" || (embedded && surface === "settings")) ? (
        <main className="admin-main-canvas p-6 max-w-5xl">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 className="text-lg font-semibold">Platform team</h2>
            <button
              type="button"
              className="aq-btn-primary text-sm"
              onClick={() => {
                setStaffInviteRole("PLATFORM_SUPPORT");
                setStaffInviteOpen(true);
              }}
            >
              Invite platform user
            </button>
          </div>
          {teamLoading ? (
            <p className="text-sm text-chat-muted">Loading team…</p>
          ) : platformStaff.length === 0 ? (
            <p className="text-sm text-chat-muted">No platform staff accounts.</p>
          ) : (
            <table className="w-full text-sm admin-card overflow-hidden">
              <thead className="bg-chat-surface-subtle text-left text-xs text-chat-muted">
                <tr>
                  <th className="p-3">Name</th>
                  <th className="p-3">Email</th>
                  <th className="p-3">Role</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {platformStaff.map((row) => (
                  <tr key={row.id} className="border-t border-chat-border">
                    <td className="p-3">{row.full_name}</td>
                    <td className="p-3">{row.email}</td>
                    <td className="p-3">{platformRoleLabel(row.platform_role)}</td>
                    <td className="p-3">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </main>
      ) : null}

      {(consoleSection === "roles" || (embedded && surface === "settings")) && permMatrix ? (
        <main className="p-6 overflow-x-auto">
          <h2 className="text-lg font-semibold mb-2">Permission matrix</h2>
          <p className="text-sm text-chat-muted mb-4">
            Generated from permissions.yaml (read-only). Custom platform roles are not supported — only the built-in
            roles below.
          </p>
          <table className="text-xs admin-card">
            <thead>
              <tr>
                <th className="p-2 text-left">Permission</th>
                {permMatrix.roles.map((r) => (
                  <th key={r} className="p-2">
                    {platformRoleLabel(r)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {permMatrix.permissions.map((perm) => (
                <tr key={perm} className="border-t border-chat-border">
                  <td className="p-2 font-mono">{perm}</td>
                  {permMatrix.roles.map((r) => (
                    <td key={r} className="p-2 text-center">
                      {permMatrix.matrix[r]?.[perm] ? "✓" : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </main>
      ) : null}

      {(consoleSection === "organizations" || (embedded && surface === "organizations")) ? (
      <div className="flex flex-col lg:flex-row min-h-[calc(100dvh-5rem)]">
        <aside
          className="w-full lg:w-[var(--admin-sidebar-width)] shrink-0 border-b lg:border-b-0 lg:border-r border-chat-border bg-[var(--color-surface)] p-4 space-y-4"
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
                  filter === f.id
                    ? "bg-chat-accent text-[var(--color-accent-fg)] border-chat-accent"
                    : "border-chat-border text-[var(--color-text-secondary)]"
                }`}
                onClick={() => setFilter(f.id)}
              >
                {f.label} {f.count}
              </button>
            ))}
          </div>
          {loading ? (
            <p className="text-sm text-chat-muted">Loading organizations…</p>
          ) : orgs.length === 0 && (counts.all ?? 0) === 0 && filter === "all" && !search.trim() ? (
            <div className="admin-card p-6 space-y-3 text-center">
              <p className="text-sm text-chat-muted">No organizations yet. The platform starts empty — create one to invite an admin and employees.</p>
              <button type="button" className="aq-btn-primary text-sm mx-auto" onClick={() => setShowNewOrg(true)}>
                Create your first organization
              </button>
            </div>
          ) : orgs.length === 0 ? (
            <p className="text-sm text-chat-muted">No organizations match your filters.</p>
          ) : (
            <ul className="space-y-2 max-h-[60vh] overflow-y-auto">
              {orgs.map((o) => (
                <li key={o.id}>
                  <div
                    className={`group relative w-full text-left admin-card p-3 transition-colors ${
                      selectedId === o.id ? "ring-2 ring-chat-brand-mark/40 bg-chat-surface-subtle" : ""
                    }`}
                  >
                  <button
                    type="button"
                    onClick={() => setSelectedId(o.id)}
                    className="w-full text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-sm truncate text-[var(--color-text-primary)]">
                        {o.name}
                        <span className="text-[var(--color-text-muted)] font-normal"> · {shortOrgId(o.id)}</span>
                      </span>
                      <span className={`text-[10px] uppercase px-2 py-0.5 rounded-full shrink-0 ${statusBadgeClass(o.license_status)}`}>
                        {licenseStatusLabel(o.license_status)}
                      </span>
                    </div>
                    <p className="text-xs text-chat-muted mt-1 capitalize">
                      {o.environment} · {formatDate(o.created_at)}
                    </p>
                    <p className="text-xs mt-2">
                      {o.seats.seats_used} / {o.seats.seats_limit} seats
                    </p>
                    <SeatBar
                      used={o.seats.seats_used}
                      limit={o.seats.seats_limit}
                      suspended={o.license_status === "suspended" || o.license_status === "expired"}
                    />
                  </button>
                    <button
                      type="button"
                      title="Delete organization"
                      aria-label={`Delete ${o.name}`}
                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 p-1.5 rounded border border-red-200 text-red-700 bg-chat-surface hover:bg-red-50 text-xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedId(o.id);
                        setDeleteOrgOpen(true);
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="admin-main-canvas flex-1 p-4 lg:p-6 min-w-0">
          {!selected ? (
            <p className="text-chat-muted text-sm">Select an organization to manage.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="admin-org-title">
                      {selected.name}
                      <span className="text-sm font-normal text-[var(--color-text-muted)] ml-2">
                        {shortOrgId(selected.id)}
                      </span>
                    </h2>
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
                    ["members", `Members ${membersTabCount}`],
                    ["license", "License"],
                    ["invitations", `Invitations ${invitationsTabCount}`],
                    ["audit", "Audit log"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    className={tab === id ? "admin-tab admin-tab-active" : "admin-tab"}
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
                    <LicenseSummaryCard org={selected} onManageLicense={() => setTab("license")} />
                  </div>

                  <div className="admin-card p-4 space-y-4">
                    <h3 className="font-medium text-sm">Invite organization admin</h3>
                    <p className="text-xs text-chat-muted">
                      Statuses: <strong>Active</strong> — member with access; <strong>Pending invite</strong> — invited
                      but not finished setup. Removed members are deleted from this organization (not shown as inactive).
                    </p>
                    {licenseBlocksInvite ? (
                      <p className="text-xs text-amber-700 border border-amber-200 rounded-lg px-3 py-2">
                        Invitations are disabled while the license is {selected.license_status} or the organization is
                        inactive. Update the license first.
                      </p>
                    ) : inviteSetup?.has_active_org_admin ? (
                      <p className="text-xs text-chat-muted">
                        An organization admin is already active. Use{" "}
                        <button type="button" className="underline" onClick={() => setTab("invitations")}>
                          Replace admin
                        </button>{" "}
                        on the Invitations tab.
                      </p>
                    ) : inviteSetup?.pending_org_admin_invite ? (
                      <p className="text-xs text-chat-muted">
                        A pending admin invitation already exists. Manage it on the{" "}
                        <button type="button" className="underline" onClick={() => setTab("invitations")}>
                          Invitations
                        </button>{" "}
                        tab.
                      </p>
                    ) : null}
                    {showInviteAdminForm ? (
                    <>
                    <p className="text-xs text-chat-muted">Platform staff can only invite the first organization administrator.</p>
                    {inviteError ? (
                      <div className="admin-inline-alert border rounded-lg px-3 py-2 text-sm flex flex-wrap gap-2 justify-between" role="alert">
                        <span>{inviteError}</span>
                        {inviteError.includes("No seats left") || inviteError.includes("no licensed seats") ? (
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
                      <input type="hidden" name="role" value="ORG_ADMIN" />
                      <button type="submit" className="aq-btn-primary md:col-span-3 w-fit" disabled={seatsFull}>
                        Send invitation
                      </button>
                    </form>
                    {lastInvite ? (
                      <div className="text-sm border border-chat-border rounded-lg p-3 space-y-2">
                        <p className="font-medium">Invitation link (expires {formatDate(lastInvite.expires)})</p>
                        <code className="block text-xs break-all">{lastInvite.url}</code>
                        <button
                          type="button"
                          className="text-xs aq-btn-primary"
                          onClick={() => navigator.clipboard.writeText(lastInvite.url)}
                        >
                          Copy link
                        </button>
                      </div>
                    ) : null}
                    </>
                    ) : null}
                  </div>

                  <div className="admin-card overflow-hidden">
                    {dirLoading ? (
                      <MembersTableSkeleton />
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
                              <td className="p-3">{roleLabel(row.role)}</td>
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
                                      className="aq-btn-danger text-xs py-1 px-2 h-auto min-h-0"
                                      onClick={async () => {
                                        if (
                                          !window.confirm(
                                            `Remove pending invitation for ${row.email}? The link will stop working.`,
                                          )
                                        ) {
                                          return;
                                        }
                                        try {
                                          await revokeInvitation(auth, selectedId, row.invitation_id!);
                                          toast.push(`Invitation removed for ${row.email}`, "ok");
                                          await refreshOrgs();
                                          await refreshDirectory();
                                        } catch (err) {
                                          toast.push(
                                            err instanceof Error ? err.message : "Failed to remove invitation",
                                            "err",
                                          );
                                        }
                                      }}
                                    >
                                      Remove
                                    </button>
                                  </>
                                ) : row.membership_id ? (
                                  <button
                                    type="button"
                                    className="aq-btn-danger text-xs py-1 px-2 h-auto min-h-0"
                                    onClick={() =>
                                      setRemoveTarget({
                                        membershipId: row.membership_id!,
                                        name: row.full_name || row.email,
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

              {tab === "invitations" && selected ? (
                <OrgInvitationsPanel session={auth} org={selected} onRefreshOrgs={refreshOrgs} />
              ) : null}

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
                <div className="admin-card p-4 text-sm space-y-3">
                  <div className="border border-chat-border rounded-lg p-3 space-y-2">
                    <p className="text-xs font-medium text-chat-muted">Setup status</p>
                    <ul className="space-y-1 text-sm">
                      <li className="flex justify-between gap-2">
                        <span>Admin invited</span>
                        <button type="button" className="text-xs underline" onClick={() => setTab("invitations")}>
                          {adminSetupLabel}
                        </button>
                      </li>
                      <li className="flex justify-between gap-2">
                        <span>Employee link</span>
                        <button type="button" className="text-xs underline" onClick={() => setTab("invitations")}>
                          Configure
                        </button>
                      </li>
                    </ul>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-[var(--color-text-muted)]">Organization ID</p>
                      <p className="font-mono text-[var(--color-text-primary)]">{selected.id}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--color-text-muted)]">Slug</p>
                      <p>{selected.slug}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--color-text-muted)]">Environment</p>
                      <p className="capitalize">{selected.environment}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--color-text-muted)]">Account status</p>
                      <p>{selected.is_active ? "Active" : "Inactive"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--color-text-muted)]">Seats</p>
                      <p>
                        {selected.seats.seats_used} / {selected.seats.seats_limit} used (
                        {selected.seats.active_members} members, {selected.seats.pending_invitations} pending invites)
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--color-text-muted)]">Owner label</p>
                      <p>{selected.owner_display_name ?? "—"}</p>
                    </div>
                  </div>
                  <p className="text-[var(--color-text-muted)] text-xs">
                    Platform console shows metadata and counts only — never tenant documents or conversations.
                  </p>
                  <div className="flex flex-wrap gap-2 pt-2">
                    <button type="button" className="aq-btn-secondary text-xs" onClick={() => setTab("members")}>
                      Manage members
                    </button>
                    <button type="button" className="aq-btn-secondary text-xs" onClick={() => setTab("license")}>
                      Edit license
                    </button>
                  </div>
                  <div className="border border-red-200 rounded-lg p-3 space-y-2 mt-4">
                    <p className="text-xs font-medium text-red-700">Danger zone</p>
                    {selected.deletion_status === "pending_deletion" ? (
                      <>
                        <p className="text-xs text-chat-muted">
                          Scheduled for permanent purge
                          {selected.purge_scheduled_at
                            ? ` on ${formatDate(selected.purge_scheduled_at)}`
                            : " after the 30-day retention period"}
                          . Members and invitations are already disabled.
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="aq-btn-secondary text-xs"
                            onClick={() =>
                              void restoreAdminOrganization(auth, selectedId).then(async () => {
                                toast.push(`${selected.name} restored`, "ok");
                                await refreshOrgs();
                              })
                            }
                          >
                            Restore organization
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <p className="text-xs text-chat-muted">
                          Permanently remove this organization after a 30-day retention period. Requires typing the
                          exact organization name.
                        </p>
                        <button
                          type="button"
                          className="aq-btn-danger text-xs"
                          onClick={() => {
                            setDeleteOrgError(null);
                            setDeleteOrgOpen(true);
                          }}
                        >
                          Delete organization
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>
      ) : null}

      <DeleteOrganizationDialog
        open={deleteOrgOpen && Boolean(selected)}
        org={selected ?? null}
        loading={deleteOrgLoading}
        errorMessage={deleteOrgError}
        onCancel={() => {
          setDeleteOrgOpen(false);
          setDeleteOrgError(null);
        }}
        onConfirm={async (confirmName) => {
          if (!selectedId || !selected) return;
          setDeleteOrgLoading(true);
          setDeleteOrgError(null);
          try {
            const deletedId = selectedId;
            const result = await deleteAdminOrganization(auth, deletedId, confirmName);
            setOrgs((prev) => prev.filter((o) => o.id !== deletedId));
            setSelectedId((id) => (id === deletedId ? "" : id));
            toast.push(
              `${selected.name} scheduled for deletion (purge in ${result.retention_days} days)`,
              "ok",
            );
            setDeleteOrgOpen(false);
            await refreshOrgs();
          } catch (err) {
            const msg = err instanceof Error ? err.message : "Delete failed";
            setDeleteOrgError(msg);
            toast.push(msg, "err");
          } finally {
            setDeleteOrgLoading(false);
          }
        }}
      />

      <RemoveMemberDialog
        open={Boolean(removeTarget && selected)}
        memberName={removeTarget?.name ?? ""}
        orgName={selected?.name ?? ""}
        loading={removeLoading}
        onCancel={() => setRemoveTarget(null)}
        onConfirm={async (reason) => {
          if (!removeTarget || !selectedId) return;
          const removedId = removeTarget.membershipId;
          const removedName = removeTarget.name;
          setRemoveLoading(true);
          try {
            await deactivateMember(auth, selectedId, removedId, reason);
            setDirectory((rows) => rows.filter((r) => r.membership_id !== removedId));
            setDirTotal((n) => Math.max(0, n - 1));
            setDirSeats((s) =>
              s
                ? {
                    ...s,
                    active_members: Math.max(0, s.active_members - 1),
                    seats_used: Math.max(0, s.seats_used - 1),
                  }
                : s,
            );
            toast.push(`${removedName} removed from ${selected?.name}`, "ok");
            setRemoveTarget(null);
            await refreshOrgs();
            await refreshDirectory();
          } catch (err) {
            toast.push(err instanceof Error ? err.message : "Remove failed", "err");
          } finally {
            setRemoveLoading(false);
          }
        }}
      />

      <InvitePlatformStaffDialog
        open={staffInviteOpen}
        defaultRole={staffInviteRole}
        loading={staffInviteLoading}
        onClose={() => setStaffInviteOpen(false)}
        onSubmit={async (payload) => {
          setStaffInviteLoading(true);
          try {
            await invitePlatformStaff(auth, payload);
            toast.push(`Invited ${payload.email}`, "ok");
            setStaffInviteOpen(false);
            setTeamLoading(true);
            fetchPlatformStaff(auth)
              .then(setPlatformStaff)
              .finally(() => setTeamLoading(false));
            const ctx = await fetchAdminContext(auth);
            setContext(ctx);
          } catch (err) {
            toast.push(err instanceof Error ? err.message : "Invite failed", "err");
          } finally {
            setStaffInviteLoading(false);
          }
        }}
      />

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
      {dirty ? <p className="text-xs text-[var(--color-warning)]">Unsaved changes</p> : null}
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

export default function PlatformAdminPage(props: PlatformAdminPageProps = {}) {
  return (
    <ToastProvider>
      <PlatformAdminInner {...props} />
    </ToastProvider>
  );
}
