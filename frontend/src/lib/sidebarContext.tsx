import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  applySidebarCollapsed,
  persistSidebarCollapsed,
  readSidebarCollapsedFromStorage,
} from "./sidebarInit";

type SidebarContextValue = {
  collapsed: boolean;
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
  toggleCollapsed: () => void;
  expand: () => void;
};

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(() => readSidebarCollapsedFromStorage());
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    applySidebarCollapsed(collapsed);
  }, [collapsed]);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((v) => {
      const next = !v;
      persistSidebarCollapsed(next);
      return next;
    });
  }, []);

  const expand = useCallback(() => {
    setCollapsed(false);
    persistSidebarCollapsed(false);
  }, []);

  const value = useMemo(
    () => ({ collapsed, mobileOpen, setMobileOpen, toggleCollapsed, expand }),
    [collapsed, mobileOpen, toggleCollapsed, expand],
  );

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
}

export function useSidebar() {
  const ctx = useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar must be used within SidebarProvider");
  return ctx;
}
