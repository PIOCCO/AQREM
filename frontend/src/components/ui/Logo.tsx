export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <div
      className={`${className} rounded-md bg-[var(--chat-brand-mark)] flex items-center justify-center text-white font-bold text-sm`}
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
      {!compact && <span className="text-[15px] font-semibold tracking-tight text-chat-fg">AQREM</span>}
    </div>
  );
}
