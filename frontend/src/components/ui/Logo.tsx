export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <div
      className={`${className} rounded-lg bg-gradient-to-br from-brand-violet to-brand-blue flex items-center justify-center text-white font-bold text-sm shadow-sm`}
      aria-hidden
    >
      A
    </div>
  );
}

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      {!compact && <span className="text-base font-semibold tracking-tight text-slate-900">AQREM</span>}
    </div>
  );
}
