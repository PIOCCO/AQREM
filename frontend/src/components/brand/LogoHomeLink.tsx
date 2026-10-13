import { Link, useLocation } from "react-router-dom";
import { Logo, type LogoVariant } from "./Logo";
import { Tooltip } from "../ui/Tooltip";
import { dispatchFocusComposer } from "../../lib/chatHome";

type Props = {
  variant: LogoVariant;
  onNavigate?: () => void;
  className?: string;
};

export function LogoHomeLink({ variant, onNavigate, className = "" }: Props) {
  const location = useLocation();
  const isHome = location.pathname === "/" || location.pathname === "/chat";

  return (
    <Tooltip label="AQREM home">
      <Link
        to="/"
        className={`aq-logo-home-link ${className}`}
        aria-label="AQREM home"
        aria-current={isHome ? "page" : undefined}
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
          onNavigate?.();
          if (location.pathname === "/" || location.pathname === "/chat") {
            e.preventDefault();
            dispatchFocusComposer();
          }
        }}
        data-testid="logo-home-link"
      >
        <Logo variant={variant} size={28} />
      </Link>
    </Tooltip>
  );
}
