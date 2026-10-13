import type { ReactNode } from "react";
import { Dialog } from "./dialog/Dialog";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="aq-card aq-card-p flex flex-col items-center justify-center gap-3 text-center" role="status">
      <span className="aq-spinner" aria-hidden />
      <p className="text-sm text-[var(--color-text-secondary)]">{label}</p>
    </div>
  );
}

export function SkeletonBlock({ className = "h-24 w-full" }: { className?: string }) {
  return <div className={`aq-skeleton ${className}`} aria-hidden />;
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="aq-alert-error" role="alert">
      <p className="font-medium mb-1">Something went wrong</p>
      <p className="mb-3 opacity-90">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="aq-btn-secondary">
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="aq-card border-dashed aq-card-p text-center">
      <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-2">{title}</h2>
      <p className="text-sm text-[var(--color-text-secondary)] max-w-md mx-auto mb-4">{description}</p>
      {action && <div className="flex justify-center">{action}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  hideTitle,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  hideTitle?: boolean;
}) {
  return (
    <header className="aq-page-header">
      <div className="min-w-0">
        {!hideTitle ? <h1 className="aq-page-title">{title}</h1> : null}
        {subtitle && <p className={`aq-page-subtitle ${hideTitle ? "mt-0" : ""}`}>{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
    </header>
  );
}

/** Subtitle-only header for shell routes where the title lives in the top bar. */
export function PageLead({ subtitle, actions }: { subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="aq-page-header">
      <div className="min-w-0">
        {subtitle ? <p className="aq-page-subtitle mt-0">{subtitle}</p> : null}
      </div>
      {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
    </header>
  );
}

/** @deprecated Prefer Dialog from ./dialog/Dialog */
export function Modal({
  title,
  children,
  onClose,
  wide,
  subtitle,
  footer,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  subtitle?: string;
  footer?: ReactNode;
}) {
  return (
    <Dialog open title={title} subtitle={subtitle} onClose={onClose} size={wide ? "wide" : "default"} footer={footer}>
      {children}
    </Dialog>
  );
}
