import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  anchorRef: React.RefObject<HTMLElement | null>;
  /** Called when the user scrolls a scrollable ancestor (e.g. chat list). */
  scrollRootRef?: React.RefObject<HTMLElement | null>;
  align?: "start" | "end";
  children: ReactNode;
  className?: string;
  minWidth?: number;
};

type Placement = "above" | "below";

export function AnchoredMenu({
  open,
  onOpenChange,
  anchorRef,
  scrollRootRef,
  align = "end",
  children,
  className = "w-40",
  minWidth = 160,
}: Props) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<React.CSSProperties>({ visibility: "hidden" });
  const [placement, setPlacement] = useState<Placement>("below");

  const close = useCallback(() => onOpenChange(false), [onOpenChange]);

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    const width = Math.max(minWidth, rect.width);
    const left =
      align === "end" ? Math.min(rect.right - width, window.innerWidth - width - 8) : Math.max(8, rect.left);
    const menuHeight = menuRef.current?.offsetHeight ?? 120;
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const placeBelow = spaceBelow >= menuHeight + 8 || spaceBelow >= spaceAbove;
    setPlacement(placeBelow ? "below" : "above");
    if (placeBelow) {
      setStyle({
        position: "fixed",
        top: rect.bottom + 4,
        left,
        width,
        zIndex: 300,
        visibility: "visible",
      });
    } else {
      setStyle({
        position: "fixed",
        bottom: window.innerHeight - rect.top + 4,
        left,
        width,
        zIndex: 300,
        visibility: "visible",
      });
    }
  }, [align, anchorRef, minWidth]);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
  }, [open, updatePosition, children]);

  useEffect(() => {
    if (!open) return;
    function onResize() {
      updatePosition();
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      if (menuRef.current?.contains(t) || anchorRef.current?.contains(t)) return;
      close();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close, anchorRef]);

  useEffect(() => {
    if (!open) return;
    const root = scrollRootRef?.current;
    if (!root) return;
    function onScroll() {
      close();
    }
    root.addEventListener("scroll", onScroll, { passive: true });
    return () => root.removeEventListener("scroll", onScroll);
  }, [open, close, scrollRootRef]);

  if (!open) return null;

  return createPortal(
    <div
      ref={menuRef}
      role="menu"
      className={`rounded-lg border border-chat-border bg-chat-surface py-1 text-sm shadow-composer ${className}`}
      style={style}
      data-placement={placement}
    >
      {children}
    </div>,
    document.body,
  );
}
