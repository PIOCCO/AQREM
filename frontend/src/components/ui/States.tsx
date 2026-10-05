import type { ReactNode } from "react";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="aq-card aq-card-p flex flex-col items-center justify-center gap-3 text-center" role="status">
      <span className="aq-spinner" aria-hidden />
      <p className="text-sm text-slate-600">{label}</p>
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
      <h2 className="text-base font-semibold text-slate-900 mb-2">{title}</h2>
      <p className="text-sm text-slate-600 max-w-md mx-auto mb-4">{description}</p>
      {action && <div className="flex justify-center">{action}</div>}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="aq-page-header">
      <div className="min-w-0">
        <h1 className="aq-page-title">{title}</h1>
        {subtitle && <p className="aq-page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
    </header>
  );
}

export function Modal({
  title,
  children,
  onClose,
  wide,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <div className="aq-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="aq-modal-title">
      <div className={`aq-modal ${wide ? "max-w-xl" : ""}`}>
        <div className="flex items-start justify-between gap-4 mb-2">
          <h2 id="aq-modal-title" className="aq-modal-title mb-0">
            {title}
          </h2>
          <button type="button" onClick={onClose} className="aq-btn-ghost px-2 py-1 text-slate-500" aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
