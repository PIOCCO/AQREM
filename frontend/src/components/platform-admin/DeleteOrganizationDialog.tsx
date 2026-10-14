import { FormEvent, useState } from "react";
import type { AdminOrganization } from "../../lib/platformAdminApi";
import { licenseStatusLabel } from "../../lib/roleLabels";

type Props = {
  open: boolean;
  org: AdminOrganization | null;
  loading: boolean;
  onCancel: () => void;
  onConfirm: (confirmName: string) => Promise<void>;
};

function shortOrgId(id: string) {
  return id.length >= 8 ? id.slice(0, 8) : id;
}

export function DeleteOrganizationDialog({ open, org, loading, onCancel, onConfirm }: Props) {
  const [typed, setTyped] = useState("");

  if (!open || !org) return null;

  const matches = typed === org.name;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!matches) return;
    await onConfirm(typed);
    setTyped("");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
      <form
        className="admin-card max-w-lg w-full p-6 space-y-4"
        onSubmit={(e) => {
          void onSubmit(e);
        }}
      >
        <h3 className="text-lg font-semibold text-red-700">Delete organization</h3>
        <p className="text-sm">
          You are about to schedule deletion of <strong>{org.name}</strong> (
          <span className="font-mono">{shortOrgId(org.id)}</span>, {org.environment} ·{" "}
          {licenseStatusLabel(org.license_status)}).
        </p>
        <div className="text-xs text-chat-muted space-y-1 border border-chat-border rounded-lg p-3">
          <p className="font-medium text-chat-fg">This will remove access and schedule purge of:</p>
          <ul className="list-disc pl-4 space-y-0.5">
            <li>Members, invitations, and employee join links</li>
            <li>License and seat assignments</li>
            <li>Documents, questionnaires, and answer library entries</li>
            <li>Vector / search index data and uploaded files</li>
          </ul>
          <p className="pt-2">Data is soft-deleted first, then permanently purged after 30 days.</p>
        </div>
        <label className="block text-sm">
          <span className="text-chat-muted">Type the organization name exactly to confirm</span>
          <input
            className="admin-input mt-1 font-mono"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="aq-btn-secondary text-sm" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button type="submit" className="aq-btn-danger text-sm" disabled={!matches || loading}>
            {loading ? "Deleting…" : "Delete organization"}
          </button>
        </div>
      </form>
    </div>
  );
}
