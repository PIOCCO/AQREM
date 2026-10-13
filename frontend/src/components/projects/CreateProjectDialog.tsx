import { FormEvent, useEffect, useRef, useState } from "react";
import { Dialog, DialogFooterActions } from "../ui/dialog/Dialog";
import { Field } from "../ui/dialog/Field";
import { SourceCreateFields } from "./SourceCreateFields";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { createProject } from "../../lib/api";
import type { AuthSession } from "../../lib/api";
import { buildInitialSourcePayload, readSourceForm } from "../../lib/sourceForm";

type Props = {
  open: boolean;
  onClose: () => void;
  session: AuthSession;
  onCreated: (project: { id: string; name: string }) => void | Promise<void>;
  returnFocusRef?: React.RefObject<HTMLElement | null>;
};

export function CreateProjectDialog({ open, onClose, session, onCreated, returnFocusRef }: Props) {
  const nameRef = useRef<HTMLInputElement>(null);
  const [creating, setCreating] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  useEffect(() => {
    if (!open) {
      setServerError(null);
      setDirty(false);
    }
  }, [open]);

  function requestClose() {
    if (creating) return;
    if (dirty) {
      setConfirmDiscard(true);
      return;
    }
    onClose();
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCreating(true);
    setServerError(null);
    const form = new FormData(e.currentTarget);
    const sourceValues = readSourceForm(form);
    const initial_source = buildInitialSourcePayload(sourceValues);
    try {
      const project = await createProject(session, {
        name: String(form.get("name")),
        description: String(form.get("description") || "") || undefined,
        initial_source,
      });
      await onCreated(project);
      onClose();
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <Dialog
        open={open}
        onClose={requestClose}
        onBackdropClick={requestClose}
        title="Create project"
        subtitle="Group sources and questionnaires under one evidence scope."
        returnFocusRef={returnFocusRef}
        initialFocusRef={nameRef}
        size="wide"
        data-testid="create-project-dialog"
        footer={
          <DialogFooterActions
            cancelLabel="Cancel"
            confirmLabel="Create project"
            onCancel={requestClose}
            confirmType="submit"
            formId="create-project-form"
            confirmLoading={creating}
          />
        }
      >
        <form
          id="create-project-form"
          onSubmit={onSubmit}
          className="space-y-4"
          onChange={() => setDirty(true)}
        >
          {serverError ? (
            <div className="aq-dialog-banner-error" role="alert">
              <p>{serverError}</p>
            </div>
          ) : null}
          <Field id="project-name" label="Project name" required>
            <input ref={nameRef} id="project-name" name="name" required className="aq-input" />
          </Field>
          <Field id="project-desc" label="Description" helper="Optional">
            <textarea id="project-desc" name="description" className="aq-textarea aq-textarea-autogrow" rows={3} />
          </Field>
          <SourceCreateFields defaultSourceName="" />
        </form>
      </Dialog>
      <ConfirmDialog
        open={confirmDiscard}
        title="Discard changes?"
        description="Your project details will be lost."
        confirmLabel="Discard"
        destructive
        onConfirm={onClose}
        onCancel={() => setConfirmDiscard(false)}
      />
    </>
  );
}
