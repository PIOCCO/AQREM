const statusStyles: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-800",
  needs_review: "bg-amber-100 text-amber-900",
  draft: "bg-slate-100 text-slate-700",
  rejected: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase();
  const label = status.replaceAll("_", " ");
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
        statusStyles[key] ?? "bg-slate-100 text-slate-700"
      }`}
    >
      {label}
    </span>
  );
}

export function ConfidenceBadge({ confidence }: { confidence?: string | null }) {
  if (!confidence) return null;
  const tone =
    confidence === "high"
      ? "bg-emerald-50 text-emerald-800"
      : confidence === "medium"
        ? "bg-amber-50 text-amber-900"
        : "bg-slate-100 text-slate-700";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${tone}`}>
      Confidence: {confidence}
    </span>
  );
}

export function EvidenceStrengthBadge({ strength }: { strength?: string | null }) {
  if (!strength) return null;
  return (
    <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-900 uppercase">
      {strength}
    </span>
  );
}
