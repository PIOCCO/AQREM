import { FormEvent, useCallback, useEffect, useState } from "react";
import { roleLabel } from "../../lib/roleLabels";
import type { AuthSession } from "../../lib/api";
import {
  createAdminInvitation,
  createEmployeeLink,
  fetchEmployeeLinkSummary,
  fetchInvitationHistory,
  fetchInvitationsSetup,
  deleteAdminInvitationRecord,
  deleteEmployeeLinkRecord,
  fetchAdminInvitationLink,
  fetchEmployeeLinkUrl,
  resendInvitation,
  sendAdminInvitationEmail,
  revokeInvitation,
  rotateEmployeeLink,
  type AdminOrganization,
  type EmployeeLinkSummary,
  invitationHistoryRecordType,
  type InvitationHistoryRow,
} from "../../lib/platformAdminApi";
import { pickInviteUrl } from "../../lib/inviteLinks";
import { copyToClipboard } from "../../lib/copyToClipboard";
import { useToast } from "../ui/Toast";

function truncateUrl(url: string, max = 52): string {
  return url.length <= max ? url : `${url.slice(0, max - 1)}…`;
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

type SecretDialog = { title: string; url: string; expires?: string; note?: string };

export function OrgInvitationsPanel({
  session,
  org,
  onRefreshOrgs,
}: {
  session: AuthSession;
  org: AdminOrganization;
  onRefreshOrgs: () => Promise<void>;
}) {
  const toast = useToast();
  const [history, setHistory] = useState<InvitationHistoryRow[]>([]);
  const [historyFilter, setHistoryFilter] = useState("all");
  const [linkSummary, setLinkSummary] = useState<EmployeeLinkSummary | null>(null);
  const [setup, setSetup] = useState<Awaited<ReturnType<typeof fetchInvitationsSetup>> | null>(null);
  const [secret, setSecret] = useState<SecretDialog | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  async function runRowAction(key: string, fn: () => Promise<void>) {
    if (busyKey) return;
    setBusyKey(key);
    try {
      await fn();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Action failed", "err");
    } finally {
      setBusyKey(null);
    }
  }

  async function resolveRowUrl(row: InvitationHistoryRow): Promise<string | null> {
    const fromHistory = pickInviteUrl(row);
    if (fromHistory) return fromHistory;
    if (row.status !== "pending") return null;
    if (invitationHistoryRecordType(row) === "admin_invitation") {
      const r = await fetchAdminInvitationLink(session, org.id, row.id);
      return pickInviteUrl(r);
    }
    const r = await fetchEmployeeLinkUrl(session, org.id, row.id);
    return pickInviteUrl(r);
  }

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [h, link, st] = await Promise.all([
        fetchInvitationHistory(session, org.id, historyFilter === "all" ? undefined : historyFilter),
        fetchEmployeeLinkSummary(session, org.id),
        fetchInvitationsSetup(session, org.id),
      ]);
      setHistory(h);
      setLinkSummary(link);
      setSetup(st);
    } catch {
      toast.push("Failed to load invitations", "err");
    } finally {
      setLoading(false);
    }
  }, [session, org.id, historyFilter, toast]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onAdminInvite(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const result = await createAdminInvitation(session, org.id, {
        email: String(form.get("email")),
        full_name: String(form.get("full_name")),
        personal_message: String(form.get("message") || "") || undefined,
        expires_days: Number(form.get("expires_days") || 7),
      });
      setSecret({
        title: "Admin invitation link",
        url: result.invitation_setup_url,
        expires: result.invitation_expires_at,
        note: result.email_sent ? "We sent this link by email as well." : "Email is not configured — copy this link now.",
      });
      (e.target as HTMLFormElement).reset();
      await reload();
      await onRefreshOrgs();
      toast.push("Admin invitation created", "ok");
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Invite failed", "err");
    }
  }

  async function onEmployeeLink(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const domainsRaw = String(form.get("domains") || "")
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean);
    const anyEmail = form.get("any_email") === "on";
    try {
      const result = await createEmployeeLink(session, org.id, {
        allowed_domains: anyEmail ? [] : domainsRaw,
        require_admin_approval: anyEmail ? true : form.get("approval") === "on",
        max_joins: form.get("max_joins") ? Number(form.get("max_joins")) : undefined,
        expires_days: form.get("no_expiry") === "on" ? null : Number(form.get("expires_days") || 30),
      });
      setSecret({
        title: "Employee join link",
        url: result.join_url,
        expires: result.expires_at ?? undefined,
        note: "Share with employees. Rotating invalidates the previous link immediately.",
      });
      await reload();
      toast.push("Employee link created", "ok");
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Link failed", "err");
    }
  }

  const seats = setup?.seats ?? org.seats;

  return (
    <div className="space-y-6">
      <div className="admin-card p-4 text-sm grid sm:grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-chat-muted">Seats</p>
          <p className="font-medium">
            {seats.seats_used} / {seats.seats_limit} used · {seats.seats_available} left
          </p>
        </div>
        <div>
          <p className="text-xs text-chat-muted">Employee link</p>
          <p className="font-medium capitalize">{linkSummary?.status ?? "Not created"}</p>
          {linkSummary?.link_id ? (
            <p className="text-xs text-chat-muted mt-1">
              {linkSummary.joined_count} joined · {linkSummary.pending_approval_count} pending approval
            </p>
          ) : null}
        </div>
        <div>
          <p className="text-xs text-chat-muted">Admin invitation</p>
          <p className="font-medium capitalize">{setup?.admin_invitation_status ?? "—"}</p>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="admin-card p-4 space-y-3">
          <h3 className="font-medium text-sm">Admin invitation</h3>
          <p className="text-xs text-chat-muted">
            Personal link for the organization license admin (single active invite; 7-day default expiry).
          </p>
          <form className="space-y-3" onSubmit={onAdminInvite}>
            <div>
              <label htmlFor="adm-name" className="text-xs font-medium">
                Full name
              </label>
              <input id="adm-name" name="full_name" className="admin-input mt-1 w-full" required />
            </div>
            <div>
              <label htmlFor="adm-email" className="text-xs font-medium">
                Work email
              </label>
              <input id="adm-email" name="email" type="email" className="admin-input mt-1 w-full" required />
            </div>
            <div>
              <label htmlFor="adm-exp" className="text-xs font-medium">
                Expires in (days)
              </label>
              <input id="adm-exp" name="expires_days" type="number" min={1} max={14} defaultValue={7} className="admin-input mt-1 w-full" />
            </div>
            <div>
              <label htmlFor="adm-msg" className="text-xs font-medium">
                Personal message (optional)
              </label>
              <textarea id="adm-msg" name="message" className="admin-input mt-1 w-full min-h-[72px]" />
            </div>
            <button type="submit" className="aq-btn-primary text-sm" disabled={org.seats.is_full}>
              Create admin invitation
            </button>
          </form>
        </div>

        <div className="admin-card p-4 space-y-3">
          <h3 className="font-medium text-sm">Employee link</h3>
          <p className="text-xs text-chat-muted">
            Joiners receive Viewer role and the &quot;All staff&quot; group only.
          </p>
          <form className="space-y-3" onSubmit={onEmployeeLink}>
            <div>
              <label htmlFor="emp-domains" className="text-xs font-medium">
                Allowed email domains
              </label>
              <input
                id="emp-domains"
                name="domains"
                placeholder="company.com, subsidiary.com"
                className="admin-input mt-1 w-full"
              />
              <label className="flex items-center gap-2 text-xs mt-2">
                <input type="checkbox" name="any_email" /> Any email, but every joiner needs admin approval
              </label>
            </div>
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" name="approval" defaultChecked={false} /> Company admin must approve each person
            </label>
            <div>
              <label htmlFor="emp-max" className="text-xs font-medium">
                Maximum joins (default: remaining seats)
              </label>
              <input id="emp-max" name="max_joins" type="number" min={1} className="admin-input mt-1 w-full" />
            </div>
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label htmlFor="emp-exp" className="text-xs font-medium">
                  Expires in (days)
                </label>
                <input id="emp-exp" name="expires_days" type="number" min={1} max={90} defaultValue={30} className="admin-input mt-1 w-full" />
              </div>
              <label className="flex items-center gap-2 text-xs pb-2">
                <input type="checkbox" name="no_expiry" /> No expiry
              </label>
            </div>
            <button type="submit" className="aq-btn-primary text-sm">
              {linkSummary?.link_id ? "Replace employee link" : "Create employee link"}
            </button>
            {linkSummary?.link_id ? (
              <button
                type="button"
                className="text-xs underline block"
                onClick={() => {
                  if (!window.confirm("Generate a new link? The old link stops working immediately.")) return;
                  void rotateEmployeeLink(session, org.id, linkSummary.link_id!).then((r) => {
                    setSecret({
                      title: "New employee link",
                      url: r.join_url ?? pickInviteUrl(r) ?? "",
                      note: "Copy the full URL below.",
                    });
                  });
                }}
              >
                Generate new link (rotate)
              </button>
            ) : null}
          </form>
        </div>
      </div>

      <div className="admin-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 className="font-medium text-sm">Invitation &amp; link history</h3>
          <select
            className="admin-input text-xs py-1"
            value={historyFilter}
            onChange={(e) => setHistoryFilter(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="accepted">Accepted</option>
            <option value="expired">Expired</option>
            <option value="revoked">Revoked / disabled</option>
          </select>
        </div>
        <p className="text-xs text-chat-muted mb-3">
          Pending rows show the live invitation URL. Revoked, expired, and accepted rows show no link (use Regenerate for
          expired or revoked admin invites). Copy link puts the URL on your clipboard and shows a confirmation toast.
        </p>
        {loading ? (
          <p className="text-sm text-chat-muted">Loading…</p>
        ) : history.length === 0 ? (
          <p className="text-sm text-chat-muted">No invitations or employee links yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-xs text-chat-muted text-left">
              <tr>
                <th className="pb-2">Type</th>
                <th className="pb-2">Details</th>
                <th className="pb-2">Invitation link</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Email</th>
                <th className="pb-2">Expires</th>
                <th className="pb-2">Created</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={`${row.record_type}-${row.id}`} className="border-t border-chat-border">
                  <td className="py-2 capitalize">
                    {invitationHistoryRecordType(row) === "employee_link" ? "Employee link" : "Admin invite"}
                  </td>
                  <td className="py-2">
                    <div>{row.invitee_full_name ? `${row.invitee_full_name} · ` : ""}{row.email}</div>
                    {invitationHistoryRecordType(row) === "employee_link" ? (
                      <div className="text-xs text-chat-muted">
                        {row.joined_count ?? 0} joined · {row.pending_approval_count ?? 0} pending approval
                      </div>
                    ) : row.role ? (
                      <div className="text-xs text-chat-muted">{roleLabel(row.role as string)}</div>
                    ) : null}
                  </td>
                  <td className="py-2 max-w-[14rem]">
                    {(() => {
                      const url = row.status === "pending" ? pickInviteUrl(row) : null;
                      if (!url) {
                        return (
                          <span className="text-xs text-chat-muted" title="Link not valid for this status">
                            —
                          </span>
                        );
                      }
                      return (
                        <a
                          href={url}
                          className="text-xs text-chat-accent hover:underline"
                          target="_blank"
                          rel="noreferrer"
                          title={url}
                        >
                          {truncateUrl(url)}
                        </a>
                      );
                    })()}
                  </td>
                  <td className="py-2 capitalize">{row.status}</td>
                  <td className="py-2 text-xs">
                    {invitationHistoryRecordType(row) === "admin_invitation" ? (
                      <>
                        <span className="capitalize">{row.email_delivery_status ?? "—"}</span>
                        {row.email_delivery_error ? (
                          <div className="text-red-600 mt-0.5 max-w-[12rem] break-words">{row.email_delivery_error}</div>
                        ) : null}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2">{formatDate(row.expires_at)}</td>
                  <td className="py-2">{formatDate(row.created_at)}</td>
                  <td className="py-2 flex flex-wrap gap-2">
                    {row.status !== "accepted" ? (
                      <button
                        type="button"
                        className="text-xs underline disabled:opacity-40"
                        disabled={Boolean(busyKey)}
                        onClick={() =>
                          void runRowAction(`copy-${row.id}`, async () => {
                            if (row.status === "expired" || row.status === "revoked") {
                              toast.push("Link no longer valid — use Regenerate first.", "err");
                              return;
                            }
                            const url = await resolveRowUrl(row);
                            if (!url) {
                              toast.push("Link unavailable for this row.", "err");
                              return;
                            }
                            const copied = await copyToClipboard(url);
                            if (copied.ok) toast.push("Link copied", "ok");
                            else {
                              setSecret({
                                title: "Copy invitation link",
                                url,
                                expires: row.expires_at ?? undefined,
                                note: "Select the link below and copy manually if clipboard is blocked.",
                              });
                            }
                          })
                        }
                      >
                        Copy link
                      </button>
                    ) : null}
                    {invitationHistoryRecordType(row) === "admin_invitation" && row.status === "pending" ? (
                      <>
                        <button
                          type="button"
                          className="text-xs underline disabled:opacity-40"
                          disabled={Boolean(busyKey)}
                          onClick={() =>
                            void runRowAction(`resend-${row.id}`, async () => {
                              await resendInvitation(session, org.id, row.id);
                              await reload();
                              await onRefreshOrgs();
                              toast.push("Invitation email resent", "ok");
                            })
                          }
                        >
                          Resend link
                        </button>
                        <button
                          type="button"
                          className="text-xs underline"
                          onClick={() =>
                            void sendAdminInvitationEmail(session, org.id, row.id)
                              .then(() => {
                                toast.push("Invitation email queued", "ok");
                                return reload();
                              })
                              .catch((err: unknown) =>
                                toast.push(err instanceof Error ? err.message : "Email send failed", "err"),
                              )
                          }
                        >
                          Resend email
                        </button>
                        <button
                          type="button"
                          className="text-xs underline disabled:opacity-40"
                          disabled={Boolean(busyKey)}
                          onClick={() =>
                            void runRowAction(`revoke-${row.id}`, async () => {
                              await revokeInvitation(session, org.id, row.id);
                              await reload();
                              await onRefreshOrgs();
                              toast.push("Invitation revoked", "ok");
                            })
                          }
                        >
                          Revoke
                        </button>
                      </>
                    ) : null}
                    {invitationHistoryRecordType(row) === "admin_invitation" &&
                    (row.status === "expired" || row.status === "revoked") ? (
                      <button
                        type="button"
                        className="text-xs underline disabled:opacity-40"
                        disabled={Boolean(busyKey)}
                        onClick={() =>
                          void runRowAction(`regen-${row.id}`, async () => {
                            const r = await fetchAdminInvitationLink(session, org.id, row.id);
                            await reload();
                            await onRefreshOrgs();
                            const url = pickInviteUrl(r);
                            if (url) {
                              const copied = await copyToClipboard(url);
                              if (copied.ok) toast.push("Link regenerated and copied", "ok");
                            } else {
                              toast.push("Regenerated but URL unavailable", "err");
                            }
                          })
                        }
                      >
                        Regenerate
                      </button>
                    ) : null}
                    {invitationHistoryRecordType(row) === "employee_link" &&
                    (row.status === "expired" || row.status === "revoked") ? (
                      <button
                        type="button"
                        className="text-xs underline disabled:opacity-40"
                        disabled={Boolean(busyKey)}
                        onClick={() =>
                          void runRowAction(`regen-link-${row.id}`, async () => {
                            const r = await rotateEmployeeLink(session, org.id, row.id);
                            await reload();
                            const url = r.join_url ?? pickInviteUrl(r) ?? "";
                            if (url) {
                              const copied = await copyToClipboard(url);
                              if (copied.ok) toast.push("Employee link regenerated and copied", "ok");
                            }
                          })
                        }
                      >
                        Regenerate
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="text-xs underline text-[var(--color-danger)] disabled:opacity-40"
                      disabled={Boolean(busyKey)}
                      onClick={() => {
                        if (!window.confirm("Delete this history row? Pending links will stop working.")) return;
                        void runRowAction(`delete-${row.id}`, async () => {
                          const recordType = invitationHistoryRecordType(row);
                          const rowId = row.id;
                          setHistory((prev) => prev.filter((r) => r.id !== rowId));
                          try {
                            if (recordType === "admin_invitation") {
                              await deleteAdminInvitationRecord(session, org.id, rowId);
                            } else {
                              await deleteEmployeeLinkRecord(session, org.id, rowId);
                            }
                            await reload();
                            await onRefreshOrgs();
                            toast.push("Deleted", "ok");
                          } catch (err) {
                            await reload();
                            throw err;
                          }
                        });
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {secret ? (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true">
          <div className="admin-card max-w-lg w-full p-6 space-y-3">
            <h2 className="text-lg font-semibold">{secret.title}</h2>
            {secret.expires ? <p className="text-xs text-chat-muted">Expires {formatDate(secret.expires)}</p> : null}
            {secret.note ? <p className="text-sm">{secret.note}</p> : null}
            <a
              href={secret.url}
              className="text-xs break-all font-mono bg-chat-surface-subtle p-2 rounded block hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              {secret.url}
            </a>
            <div className="flex gap-2 justify-end">
              <button type="button" className="text-sm px-3 py-2" onClick={() => setSecret(null)}>
                Close
              </button>
              <button
                type="button"
                className="aq-btn-primary text-sm"
                onClick={() => {
                  void copyToClipboard(secret.url).then((result) => {
                    if (result.ok) toast.push("Copied", "ok");
                    else toast.push("Copy failed — select the link manually", "err");
                  });
                }}
              >
                Copy link
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
