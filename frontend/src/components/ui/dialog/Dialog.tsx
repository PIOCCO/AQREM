import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Button } from "./Button";
import { useBodyScrollLock } from "./useBodyScrollLock";
import { useFocusTrap } from "./useFocusTrap";

export type DialogProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Element to restore focus on close */
  returnFocusRef?: React.RefObject<HTMLElement | null>;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  onBackdropClick?: () => void;
  size?: "default" | "wide";
  "data-testid"?: string;
};

export function Dialog({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  returnFocusRef,
  initialFocusRef,
  onBackdropClick,
  size = "default",
  "data-testid": testId = "aq-dialog",
}: DialogProps) {
  const titleId = useId();
  const descId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  useBodyScrollLock(open);
  useFocusTrap(panelRef, open);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => {
      (initialFocusRef?.current ?? panelRef.current?.querySelector<HTMLElement>(FOCUSABLE_FIRST))?.focus();
    }, 0);
    return () => window.clearTimeout(t);
  }, [open, initialFocusRef]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (open) return;
    returnFocusRef?.current?.focus();
  }, [open, returnFocusRef]);

  if (!open) return null;

  const handleBackdrop = () => {
    if (onBackdropClick) onBackdropClick();
    else onClose();
  };

  return createPortal(
    <div
      className="aq-dialog-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) handleBackdrop();
      }}
    >
      <div
        ref={panelRef}
        className={`aq-dialog ${size === "wide" ? "aq-dialog-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? descId : undefined}
        data-testid={testId}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="aq-dialog-header">
          <div className="min-w-0 flex-1 pr-3">
            <h2 id={titleId} className="aq-dialog-title">
              {title}
            </h2>
            {subtitle ? (
              <p id={descId} className="aq-dialog-subtitle">
                {subtitle}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            className="aq-dialog-close"
            aria-label="Close"
            title="Close"
            onClick={onClose}
            data-testid="dialog-close"
          >
            <span aria-hidden>×</span>
          </button>
        </header>
        <div className="aq-dialog-body">{children}</div>
        {footer ? <footer className="aq-dialog-footer">{footer}</footer> : null}
      </div>
    </div>,
    document.body,
  );
}

const FOCUSABLE_FIRST = 'input:not([disabled]),textarea:not([disabled]),button:not([disabled]),[tabindex="0"]';

export function DialogFooterActions({
  cancelLabel = "Cancel",
  confirmLabel,
  onCancel,
  onConfirm,
  confirmDisabled,
  confirmLoading,
  confirmType = "submit",
  confirmTitle,
  formId,
}: {
  cancelLabel?: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm?: () => void;
  confirmDisabled?: boolean;
  confirmLoading?: boolean;
  confirmType?: "button" | "submit";
  confirmTitle?: string;
  formId?: string;
}) {
  return (
    <>
      <Button variant="ghost" onClick={onCancel} type="button">
        {cancelLabel}
      </Button>
      <Button
        variant="primary"
        type={confirmType}
        form={formId}
        onClick={onConfirm}
        disabled={confirmDisabled}
        loading={confirmLoading}
        title={confirmTitle}
        data-testid="dialog-confirm"
      >
        {confirmLoading ? "Creating…" : confirmLabel}
      </Button>
    </>
  );
}
