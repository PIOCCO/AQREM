import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Combobox } from "../ui/dialog/Combobox";
import { Dialog, DialogFooterActions } from "../ui/dialog/Dialog";
import { Field } from "../ui/dialog/Field";
import { FileDropzone } from "../ui/dialog/FileDropzone";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { useToast } from "../ui/Toast";
import { createQuestionnaire, fetchQuestionnaires, uploadQuestionnaireFileWithProgress } from "../../lib/api";
import type { AuthSession } from "../../lib/api";
import {
  downloadQuestionnaireTemplateCsv,
  parseQuestionnaireFile,
  QUESTIONNAIRE_ACCEPT,
  QUESTIONNAIRE_MAX_BYTES,
  QUESTIONNAIRE_MAX_ROWS,
  type ParsedQuestionnaire,
} from "../../lib/questionnaireFileParse";

const DESC_MAX = 2000;

type ProjectOption = { id: string; name: string; source_count?: number };

type Props = {
  open: boolean;
  onClose: () => void;
  session: AuthSession;
  projects: ProjectOption[];
  defaultProjectId?: string | null;
  returnFocusRef?: React.RefObject<HTMLElement | null>;
  onRequestCreateProject: () => void;
};

function isDirty(state: {
  name: string;
  projectId: string;
  requestedBy: string;
  description: string;
  file: File | null;
}) {
  return Boolean(state.name.trim() || state.requestedBy.trim() || state.description.trim() || state.file);
}

export default function NewQuestionnaireDialog({
  open,
  onClose,
  session,
  projects,
  defaultProjectId,
  returnFocusRef,
  onRequestCreateProject,
}: Props) {
  const toast = useToast();
  const navigate = useNavigate();
  const nameRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState("");
  const [projectId, setProjectId] = useState(defaultProjectId ?? "");
  const [requestedBy, setRequestedBy] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [parsed, setParsed] = useState<ParsedQuestionnaire | null>(null);
  const [parsing, setParsing] = useState(false);
  const [sheetName, setSheetName] = useState("");
  const [questionColumn, setQuestionColumn] = useState("");
  const [stripDuplicates, setStripDuplicates] = useState(false);
  const [nameTouched, setNameTouched] = useState(false);
  const [projectTouched, setProjectTouched] = useState(false);
  const [fileTouched, setFileTouched] = useState(false);
  const [duplicateName, setDuplicateName] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  useEffect(() => {
    if (!open) return;
    setProjectId(defaultProjectId ?? projects[0]?.id ?? "");
    setName("");
    setRequestedBy("");
    setDescription("");
    setFile(null);
    setParsed(null);
    setServerError(null);
    setUploadProgress(null);
    setNameTouched(false);
    setProjectTouched(false);
    setFileTouched(false);
    setDuplicateName(false);
    setStripDuplicates(false);
  }, [open, defaultProjectId, projects]);

  const projectOptions = useMemo(
    () =>
      projects.map((p) => ({
        value: p.id,
        label: p.name,
        meta: p.source_count != null ? `${p.source_count} sources` : undefined,
      })),
    [projects],
  );

  const reparse = useCallback(
    async (f: File, sheet?: string, col?: string, strip?: boolean) => {
      setParsing(true);
      const result = await parseQuestionnaireFile(f, {
        sheetName: sheet,
        questionColumn: col,
        stripDuplicates: strip,
      });
      setParsed(result);
      if (result.ok) {
        setSheetName(result.selectedSheet);
        setQuestionColumn(result.questionColumn);
      }
      setParsing(false);
    },
    [],
  );

  useEffect(() => {
    if (!file) {
      setParsed(null);
      return;
    }
    void reparse(file, sheetName, questionColumn, stripDuplicates);
  }, [file, sheetName, questionColumn, stripDuplicates, reparse]);

  useEffect(() => {
    if (!open || !projectId || !name.trim()) {
      setDuplicateName(false);
      return;
    }
    let cancelled = false;
    fetchQuestionnaires(session, projectId)
      .then((rows) => {
        if (cancelled) return;
        const dup = rows.some((r: { name: string }) => r.name.trim().toLowerCase() === name.trim().toLowerCase());
        setDuplicateName(dup);
      })
      .catch(() => setDuplicateName(false));
    return () => {
      cancelled = true;
    };
  }, [open, session, projectId, name]);

  const nameError =
    nameTouched && !name.trim()
      ? "Enter a questionnaire name."
      : name.length > 120
        ? "Name must be 120 characters or fewer."
        : null;
  const projectError = projectTouched && !projectId ? "Select a project." : null;
  const fileError =
    fileTouched && !file
      ? "Add a questions file."
      : parsed && !parsed.ok
        ? parsed.error ?? "Invalid file."
        : null;

  const canSubmit =
    Boolean(name.trim() && name.length <= 120 && projectId && file && parsed?.ok && !submitting && !parsing);

  const missingHint = useMemo(() => {
    const parts: string[] = [];
    if (!name.trim()) parts.push("name");
    if (!projectId) parts.push("project");
    if (!file || !parsed?.ok) parts.push("valid questions file");
    return parts.length ? `Missing: ${parts.join(", ")}` : undefined;
  }, [name, projectId, file, parsed]);

  function requestClose() {
    if (submitting) return;
    if (isDirty({ name, projectId, requestedBy, description, file })) {
      setConfirmDiscard(true);
      return;
    }
    onClose();
  }

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    setNameTouched(true);
    setProjectTouched(true);
    setFileTouched(true);
    if (!canSubmit) {
      if (!name.trim()) nameRef.current?.focus();
      return;
    }
    setSubmitting(true);
    setServerError(null);
    try {
      const qn = await createQuestionnaire(session, {
        name: name.trim(),
        project_id: projectId,
        recipient: requestedBy.trim() || undefined,
        description: description.trim() || undefined,
      });
      setUploadProgress(0);
      const result = await uploadQuestionnaireFileWithProgress(session, qn.id, file!, setUploadProgress);
      toast.push("Questionnaire created");
      onClose();
      navigate(`/questionnaires/${qn.id}`);
      void result;
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Failed to create questionnaire");
    } finally {
      setSubmitting(false);
      setUploadProgress(null);
    }
  }

  return (
    <>
      <Dialog
        open={open}
        onClose={requestClose}
        onBackdropClick={requestClose}
        title="New questionnaire"
        subtitle="Upload the questions you need to answer and AQREM will draft responses from your evidence."
        returnFocusRef={returnFocusRef}
        initialFocusRef={nameRef}
        data-testid="new-questionnaire-dialog"
        footer={
          <DialogFooterActions
            cancelLabel="Cancel"
            confirmLabel="Create questionnaire"
            onCancel={requestClose}
            confirmType="submit"
            confirmDisabled={!canSubmit}
            confirmLoading={submitting}
            confirmTitle={missingHint}
            formId="new-questionnaire-form"
          />
        }
      >
        <form id="new-questionnaire-form" onSubmit={handleSubmit} className="space-y-4">
          {serverError ? (
            <div className="aq-dialog-banner-error" role="alert">
              <p>{serverError}</p>
              <button type="button" className="aq-link text-sm font-medium" onClick={() => void handleSubmit()}>
                Retry
              </button>
            </div>
          ) : null}

          <Field
            id="qn-name"
            label="Questionnaire name"
            required
            helper='For example, SOC 2 - Northwind'
            error={nameError}
            counter={`${name.length}/120`}
          >
            <input
              ref={nameRef}
              id="qn-name"
              className={`aq-input ${nameError ? "aq-input-error" : ""}`}
              value={name}
              maxLength={120}
              disabled={submitting}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setNameTouched(true)}
              data-testid="qn-name-input"
            />
            {duplicateName ? (
              <p className="aq-field-warning mt-1" role="status">
                A questionnaire with this name already exists in this project.
              </p>
            ) : null}
          </Field>

          <Field id="qn-project" label="Project" required helper="Questions are scoped to project evidence." error={projectError}>
            <Combobox
              id="qn-project"
              value={projectId}
              onChange={(v) => {
                setProjectId(v);
                setProjectTouched(true);
              }}
              options={projectOptions}
              placeholder="Select project"
              disabled={submitting}
              error={projectError}
              emptyState={
                <div className="text-center space-y-2">
                  <p className="text-sm text-[var(--color-text-muted)]">No projects yet</p>
                  <button type="button" className="aq-btn-secondary text-sm" onClick={onRequestCreateProject}>
                    Create project
                  </button>
                </div>
              }
              data-testid="qn-project-combobox"
            />
          </Field>

          <Field
            id="qn-requested-by"
            label="Requested by"
            helper="Who asked for this questionnaire (company or contact)"
          >
            <input
              id="qn-requested-by"
              className="aq-input"
              value={requestedBy}
              disabled={submitting}
              onChange={(e) => setRequestedBy(e.target.value)}
            />
          </Field>

          <Field
            id="qn-description"
            label="Description"
            counter={`${description.length}/${DESC_MAX}`}
            helper="Optional context for your team"
          >
            <textarea
              id="qn-description"
              className="aq-textarea aq-textarea-autogrow"
              value={description}
              maxLength={DESC_MAX}
              disabled={submitting}
              rows={3}
              onChange={(e) => {
                setDescription(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 6 * 24)}px`;
              }}
            />
          </Field>

          <Field
            id="qn-file"
            label="Questions file"
            required
            helper={`CSV or XLSX · max ${QUESTIONNAIRE_MAX_BYTES / (1024 * 1024)} MB · up to ${QUESTIONNAIRE_MAX_ROWS} questions`}
            error={fileError}
          >
            <FileDropzone
              id="qn-file"
              accept={QUESTIONNAIRE_ACCEPT}
              maxBytes={QUESTIONNAIRE_MAX_BYTES}
              file={file}
              disabled={submitting}
              error={fileError}
              uploadProgress={uploadProgress}
              onDownloadTemplate={downloadQuestionnaireTemplateCsv}
              onFile={(f) => {
                setFile(f);
                setFileTouched(true);
              }}
            />
          </Field>

          {parsing ? <p className="text-sm text-[var(--color-text-muted)]">Analyzing file…</p> : null}

          {parsed?.ok ? (
            <div className="aq-dialog-preview" data-testid="qn-file-preview">
              <p className="text-sm font-medium">
                Found {parsed.rowCount} question{parsed.rowCount === 1 ? "" : "s"}
                {parsed.sheets.length > 1 || parsed.selectedSheet !== "CSV"
                  ? ` in sheet '${parsed.selectedSheet}'`
                  : ""}
              </p>
              {parsed.sheets.length > 1 ? (
                <Field id="qn-sheet" label="Sheet">
                  <Combobox
                    id="qn-sheet"
                    value={sheetName}
                    onChange={setSheetName}
                    options={parsed.sheets.map((s) => ({ value: s.name, label: s.name, meta: `${s.rowCount} rows` }))}
                    data-testid="qn-sheet-combobox"
                  />
                </Field>
              ) : null}
              {parsed.columns.length > 1 ? (
                <Field id="qn-column" label="Question column">
                  <Combobox
                    id="qn-column"
                    value={questionColumn}
                    onChange={setQuestionColumn}
                    options={parsed.columns.map((c) => ({ value: c, label: c }))}
                    data-testid="qn-column-combobox"
                  />
                </Field>
              ) : null}
              {parsed.duplicateQuestions.length > 0 ? (
                <div className="aq-field-warning space-y-2">
                  <p>{parsed.duplicateQuestions.length} duplicate question(s) detected.</p>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={stripDuplicates}
                      onChange={(e) => setStripDuplicates(e.target.checked)}
                    />
                    Remove duplicates before upload
                  </label>
                </div>
              ) : null}
              {parsed.previewRows.length > 0 ? (
                <div className="overflow-x-auto mt-2">
                  <table className="aq-table text-xs">
                    <thead>
                      <tr>
                        {parsed.columns.slice(0, 4).map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {parsed.previewRows.map((row, i) => (
                        <tr key={i}>
                          {row.map((cell, j) => (
                            <td key={j} className="max-w-[8rem] truncate">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ) : null}
        </form>
      </Dialog>

      <ConfirmDialog
        open={confirmDiscard}
        title="Discard this questionnaire?"
        description="Your entries will be lost if you close now."
        confirmLabel="Discard"
        destructive
        onConfirm={onClose}
        onCancel={() => setConfirmDiscard(false)}
      />
    </>
  );
}
