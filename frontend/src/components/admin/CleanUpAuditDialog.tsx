import { useId, useState } from "react";
import { Dialog } from "../ui/dialog/Dialog";

export type AuditCleanupScope = "older_than_7d" | "older_than_30d" | "all";

const SCOPE_OPTIONS: { value: AuditCleanupScope; label: string }[] = [
  { value: "older_than_7d", label: "Older than 7 days" },
  { value: "older_than_30d", label: "Older than 30 days" },
  { value: "all", label: "All logs" },
];

type Props = {
  open: boolean;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: (scope: AuditCleanupScope) => void;
};

export function CleanUpAuditDialog({ open, loading, onCancel, onConfirm }: Props) {
  const scopeId = useId();
  const confirmId = useId();
  const [scope, setScope] = useState<AuditCleanupScope>("older_than_30d");
  const [confirmText, setConfirmText] = useState("");

  const needsDeleteWord = scope === "all";
  const confirmEnabled = !loading && (!needsDeleteWord || confirmText.trim().toUpperCase() === "DELETE");

  return (
    <Dialog
      open={open}
      onClose={() => !loading && onCancel()}
      title="Delete audit logs?"
      footer={
        <>
          <button type="button" className="admin-btn-secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button
            type="button"
            className="aq-btn-danger min-h-10 px-4"
            disabled={!confirmEnabled}
            onClick={() => onConfirm(scope)}
          >
            {loading ? "Cleaning…" : "Delete"}
          </button>
        </>
      }
    >
      <div className="space-y-4 text-sm text-chat-muted">
        <p>This permanently deletes the audit logs of your organization. This cannot be undone.</p>
        <div>
          <label htmlFor={scopeId} className="block text-sm font-medium mb-1">
            Scope
          </label>
          <select
            id={scopeId}
            className="admin-input w-full"
            value={scope}
            onChange={(e) => {
              setScope(e.target.value as AuditCleanupScope);
              setConfirmText("");
            }}
            disabled={loading}
          >
            {SCOPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        {needsDeleteWord ? (
          <div>
            <label htmlFor={confirmId} className="block text-sm font-medium mb-1">
              Type DELETE to confirm
            </label>
            <input
              id={confirmId}
              className="admin-input w-full"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoComplete="off"
              disabled={loading}
            />
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}
