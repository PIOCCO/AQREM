import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "secondary" | "danger";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
  children: ReactNode;
};

const variantClass: Record<Variant, string> = {
  primary: "aq-btn-primary",
  ghost: "aq-btn-ghost",
  secondary: "aq-btn-secondary",
  danger: "aq-btn-danger",
};

export function Button({ variant = "primary", loading, disabled, className = "", type = "button", children, ...rest }: Props) {
  return (
    <button
      type={type}
      className={`${variantClass[variant]} inline-flex items-center justify-center gap-2 ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <span className="aq-spinner" aria-hidden /> : null}
      {children}
    </button>
  );
}
