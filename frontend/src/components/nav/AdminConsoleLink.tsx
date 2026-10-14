import { NavLink, useLocation } from "react-router-dom";
import { IconShield } from "../icons/Icons";
import { Tooltip } from "../ui/Tooltip";

type Props = {
  variant: "sidebar" | "rail" | "menu";
  onNavigate?: () => void;
};

export function AdminConsoleLink({ variant, onNavigate }: Props) {
  const location = useLocation();
  const inAdmin = location.pathname.startsWith("/org-admin") || location.pathname.startsWith("/admin");

  if (variant === "rail") {
    return (
      <Tooltip label="Admin console">
        <NavLink
          to="/org-admin"
          onClick={onNavigate}
          className={({ isActive }) => `sidebar-rail-btn ${isActive || inAdmin ? "sidebar-rail-btn-active" : ""}`}
          aria-label="Admin console"
          aria-current={inAdmin ? "page" : undefined}
          data-testid="admin-console-link-rail"
        >
          <IconShield className="h-5 w-5" />
        </NavLink>
      </Tooltip>
    );
  }

  if (variant === "menu") {
    return (
      <NavLink to="/org-admin" className="chat-menu-item block" onClick={onNavigate} data-testid="admin-console-link-menu">
        Admin console
      </NavLink>
    );
  }

  return (
    <NavLink
      to="/org-admin"
      onClick={onNavigate}
      className={({ isActive }) => `ref-nav-item ${isActive || inAdmin ? "ref-nav-item-active" : ""}`}
      aria-label="Admin console"
      aria-current={inAdmin ? "page" : undefined}
      data-testid="admin-console-link"
    >
      <IconShield className="h-[18px] w-[18px] shrink-0 opacity-80" />
      <span className="flex-1 truncate">Admin console</span>
    </NavLink>
  );
}
