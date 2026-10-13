import { FormEvent, useEffect, useId, useRef } from "react";
import { Dialog } from "../ui/dialog/Dialog";
import { platformRoleLabel } from "../../lib/roleLabels";

const PLATFORM_ROLES = ["SUPER_ADMIN", "PLATFORM_SUPPORT", "PLATFORM_BILLING"] as const;

type Props = {
  open: boolean;
  defaultRole?: (typeof PLATFORM_ROLES)[number];
  loading?: boolean;
  onSubmit: (payload: { full_name: string; email: string; role: string }) => void;
  onClose: () => void;
};

export function InvitePlatformStaffDialog({
  open,
  defaultRole = "PLATFORM_SUPPORT",
  loading,
  onSubmit,
  onClose,
}: Props) {
  const formId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    onSubmit({
      full_name: String(form.get("full_name")),
      email: String(form.get("email")),
      role: String(form.get("role")),
    });
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Invite platform user"
      footer={
        <>
          <button ref={cancelRef} type="button" className="aq-btn-ghost" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          <button type="submit" form={formId} className="aq-btn-primary" disabled={loading}>
            {loading ? "Sending…" : "Send invite"}
          </button>
        </>
      }
    >
      <form id={formId} className="space-y-3" onSubmit={handleSubmit}>
        {defaultRole === "SUPER_ADMIN" ? (
          <p className="text-xs admin-inline-alert border rounded px-3 py-2" role="note">
            Granting super admin may require two-person approval on the server. If invite fails, use an existing super
            admin account or contact operations.
          </p>
        ) : null}
        <div>
          <label className="text-xs font-medium" htmlFor={`${formId}-name`}>
            Full name
          </label>
          <input id={`${formId}-name`} name="full_name" className="admin-input mt-1 w-full" required />
        </div>
        <div>
          <label className="text-xs font-medium" htmlFor={`${formId}-email`}>
            Work email
          </label>
          <input id={`${formId}-email`} name="email" type="email" className="admin-input mt-1 w-full" required />
        </div>
        <div>
          <span className="text-xs font-medium">Platform role</span>
          <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="Platform role">
            {PLATFORM_ROLES.map((role) => (
              <label
                key={role}
                className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-xs cursor-pointer hover:bg-[var(--color-surface-raised)]"
              >
                <input
                  type="radio"
                  name="role"
                  value={role}
                  defaultChecked={role === defaultRole}
                  className="accent-[var(--color-accent)]"
                />
                {platformRoleLabel(role)}
              </label>
            ))}
          </div>
        </div>
      </form>
    </Dialog>
  );
}
