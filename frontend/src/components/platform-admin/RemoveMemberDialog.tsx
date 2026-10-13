import { useEffect, useId, useRef, useState } from "react";
import { Dialog } from "../ui/dialog/Dialog";

type Props = {
  open: boolean;
  memberName: string;
  orgName: string;
  loading?: boolean;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
};

export function RemoveMemberDialog({ open, memberName, orgName, loading, onConfirm, onCancel }: Props) {
  const reasonId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
      cancelRef.current?.focus();
    }
  }, [open]);

  const valid = reason.trim().length >= 3;

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={`Remove ${memberName} from ${orgName}?`}
      data-testid="remove-member-dialog"
      footer={
        <>
          <button ref={cancelRef} type="button" className="aq-btn-ghost" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button
            type="button"
            className="aq-btn-danger"
            disabled={!valid || loading}
            onClick={() => onConfirm(reason.trim())}
          >
            {loading ? "Removing…" : "Remove member"}
          </button>
        </>
      }
    >
      <div className="space-y-3 text-sm text-[var(--color-text-secondary)]">
        <p>
          They will lose access immediately, their seat will be freed, and their content stays with the organization.
          This is recorded in the organization audit log as a platform action.
        </p>
        <div>
          <label htmlFor={reasonId} className="block text-xs font-medium text-[var(--color-text-primary)] mb-1">
            Reason (required)
          </label>
          <textarea
            id={reasonId}
            className="aq-textarea min-h-[4rem] w-full"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why is this member being removed?"
            required
            minLength={3}
          />
        </div>
      </div>
    </Dialog>
  );
}
