import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type SidebarMenuContextValue = {
  openMenuId: string | null;
  setOpenMenuId: (id: string | null) => void;
};

const SidebarMenuContext = createContext<SidebarMenuContextValue | null>(null);

export function SidebarMenuProvider({ children }: { children: ReactNode }) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const value = useMemo(() => ({ openMenuId, setOpenMenuId }), [openMenuId]);
  return <SidebarMenuContext.Provider value={value}>{children}</SidebarMenuContext.Provider>;
}

export function useSidebarMenu() {
  const ctx = useContext(SidebarMenuContext);
  if (!ctx) throw new Error("useSidebarMenu requires SidebarMenuProvider");
  return ctx;
}
