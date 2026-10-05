const statusConfig: Record<string, { className: string; symbol: string }> = {
  approved: { className: "bg-success-bg text-success-text border-success-border", symbol: "✓" },
  needs_review: { className: "bg-warning-bg text-warning-text border-warning-border", symbol: "⚠" },
  potentially_stale: { className: "bg-warning-bg text-warning-text border-warning-border", symbol: "⚠" },
  draft: { className: "bg-surface-subtle text-slate-700 border-border", symbol: "○" },
  rejected: { className: "bg-error-bg text-error-text border-error-border", symbol: "✕" },
  failed: { className: "bg-error-bg text-error-text border-error-border", symbol: "✕" },
  indexing: { className: "bg-info-bg text-info-text border-info-border", symbol: "…" },
  processing: { className: "bg-info-bg text-info-text border-info-border", symbol: "…" },
  ready: { className: "bg-success-bg text-success-text border-success-border", symbol: "✓" },
};

function BadgeShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${className}`}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase();
  const cfg = statusConfig[key] ?? statusConfig.draft;
  const label = status.replaceAll("_", " ");
  return (
    <BadgeShell className={cfg.className}>
      <span aria-hidden>{cfg.symbol}</span>
      {label}
    </BadgeShell>
  );
}

export function ConfidenceBadge({ confidence }: { confidence?: string | null }) {
  if (!confidence) return null;
  const tone =
    confidence === "high"
      ? "bg-success-bg text-success-text border-success-border"
      : confidence === "medium"
        ? "bg-warning-bg text-warning-text border-warning-border"
        : "bg-surface-subtle text-slate-700 border-border";
  return (
    <BadgeShell className={tone}>
      <span className="normal-case text-[11px]">Confidence:</span> {confidence}
    </BadgeShell>
  );
}

export function InsufficientEvidenceBadge() {
  return (
    <BadgeShell className="bg-warning-bg text-warning-text border-warning-border">
      <span aria-hidden>⚠</span>
      Insufficient evidence
    </BadgeShell>
  );
}

export function EvidenceStrengthBadge({ strength }: { strength?: string | null }) {
  if (!strength) return null;
  return (
    <BadgeShell className="bg-info-bg text-info-text border-info-border uppercase tracking-wide">
      {strength}
    </BadgeShell>
  );
}
