import type { ReactNode } from "react";

type Props = {
  id: string;
  label: ReactNode;
  required?: boolean;
  helper?: ReactNode;
  error?: string | null;
  counter?: string;
  children: ReactNode;
};

export function Field({ id, label, required, helper, error, counter, children }: Props) {
  return (
    <div className="aq-field">
      <div className="flex items-baseline justify-between gap-2 mb-1.5">
        <label htmlFor={id} className="aq-field-label-visible">
          {label}
          {required ? (
            <span className="text-[var(--color-danger)] ml-0.5" aria-hidden>
              *
            </span>
          ) : null}
        </label>
        {counter ? <span className="text-xs text-[var(--color-text-muted)] tabular-nums">{counter}</span> : null}
      </div>
      {children}
      {helper && !error ? <p className="aq-field-helper">{helper}</p> : null}
      {error ? (
        <p className="aq-field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
