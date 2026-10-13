import { useId, useRef, useState, type DragEvent } from "react";
import { Button } from "./Button";

type Props = {
  id: string;
  accept: string;
  maxBytes: number;
  file: File | null;
  onFile: (file: File | null) => void;
  disabled?: boolean;
  error?: string | null;
  hint?: string;
  onDownloadTemplate?: () => void;
  uploadProgress?: number | null;
  "data-testid"?: string;
};

export function FileDropzone({
  id,
  accept,
  maxBytes,
  file,
  onFile,
  disabled,
  error,
  hint,
  onDownloadTemplate,
  uploadProgress,
  "data-testid": testId = "file-dropzone",
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const descId = useId();

  function pick(f: File | null) {
    onFile(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) pick(f);
  }

  const maxMb = (maxBytes / (1024 * 1024)).toFixed(0);

  return (
    <div className="space-y-2">
      {!file ? (
        <div
          role="button"
          tabIndex={0}
          aria-describedby={descId}
          data-testid={testId}
          className={`aq-dropzone ${dragOver ? "aq-dropzone-active" : ""} ${error ? "aq-dropzone-error" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          onClick={() => !disabled && inputRef.current?.click()}
        >
          <p className="text-sm font-medium text-[var(--color-text-primary)]">Drag and drop or click to browse</p>
          <p id={descId} className="text-xs text-[var(--color-text-muted)] mt-1">
            {hint ?? `CSV or XLSX · max ${maxMb} MB`}
          </p>
          <input
            ref={inputRef}
            id={id}
            type="file"
            accept={accept}
            className="sr-only"
            disabled={disabled}
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />
        </div>
      ) : (
        <div className="aq-file-chip" data-testid={`${testId}-chip`}>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">{file.name}</p>
            <p className="text-xs text-[var(--color-text-muted)]">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
          <Button variant="ghost" type="button" className="text-sm py-1 px-2" onClick={() => pick(null)} disabled={disabled}>
            Remove
          </Button>
        </div>
      )}
      {uploadProgress != null ? (
        <div className="aq-progress-track" aria-label="Upload progress">
          <div className="aq-progress-fill transition-all duration-200" style={{ width: `${uploadProgress}%` }} />
        </div>
      ) : null}
      {onDownloadTemplate ? (
        <button type="button" className="aq-link text-xs" onClick={onDownloadTemplate}>
          Download template
        </button>
      ) : null}
    </div>
  );
}
