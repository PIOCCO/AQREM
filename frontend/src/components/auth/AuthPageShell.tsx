import type { ReactNode } from "react";
import { Logo } from "../brand/Logo";
import { getUiBuildLabel } from "../../lib/buildInfo";

type AuthPageShellProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
};

/** Shared layout for all unauthenticated auth flows (login, invite, password). */
export function AuthPageShell({ title, subtitle, children, footer }: AuthPageShellProps) {
  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-[var(--color-background)] p-6 font-sans">
      <div className="w-full max-w-[440px] aq-card shadow-panel aq-card-p">
        <div className="mb-6 flex flex-col items-center text-center">
          <Logo variant="mark" size={48} />
          <p className="text-[var(--color-text-muted)] mt-4 text-sm">
            {subtitle ?? "Evidence-backed questionnaire responses"}
          </p>
        </div>
        <h1 className="text-lg font-semibold mb-4 text-[var(--color-text-primary)]">{title}</h1>
        {children}
        {footer ? <div className="mt-4">{footer}</div> : null}
        <p className="text-[10px] text-[var(--color-text-muted)] mt-6 text-center font-mono" data-testid="ui-build-label">
          UI build {getUiBuildLabel()}
        </p>
      </div>
    </div>
  );
}
