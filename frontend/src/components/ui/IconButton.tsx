import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Tooltip } from "./Tooltip";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  children: ReactNode;
  variant?: "ghost" | "surface";
};

export function IconButton({ label, children, variant = "ghost", className = "", disabled, ...rest }: Props) {
  const base =
    variant === "surface"
      ? "ref-header-icon-btn"
      : "inline-flex h-9 w-9 min-h-[32px] min-w-[32px] items-center justify-center rounded-lg text-chat-muted transition-colors duration-150 hover:bg-chat-hover hover:text-chat-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent";

  return (
    <Tooltip label={disabled && rest.title ? rest.title : label}>
      <button
        type="button"
        aria-label={label}
        disabled={disabled}
        className={`${base} ${className}`.trim()}
        {...rest}
      >
        {children}
      </button>
    </Tooltip>
  );
}
