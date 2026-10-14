import { useCallback, useRef, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  disabled?: boolean;
  disabledReason?: string | null;
  onFiles: (files: File[]) => void;
  className?: string;
};

export default function ChatFileDropOverlay({ children, disabled, disabledReason, onFiles, className = "" }: Props) {
  const dragDepth = useRef(0);
  const overlayRef = useRef<HTMLDivElement>(null);

  const hideOverlay = useCallback(() => {
    dragDepth.current = 0;
    overlayRef.current?.classList.remove("chat-drop-overlay--visible");
  }, []);

  const showOverlay = useCallback(() => {
    overlayRef.current?.classList.add("chat-drop-overlay--visible");
  }, []);

  return (
    <div
      className={`chat-drop-root relative ${className}`.trim()}
      onDragEnter={(e) => {
        if (disabled) return;
        if (!e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();
        dragDepth.current += 1;
        if (dragDepth.current === 1) showOverlay();
      }}
      onDragOver={(e) => {
        if (disabled) return;
        if (!e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }}
      onDragLeave={(e) => {
        if (disabled) return;
        if (!e.dataTransfer.types.includes("Files")) return;
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) hideOverlay();
      }}
      onDrop={(e) => {
        hideOverlay();
        if (disabled) return;
        e.preventDefault();
        const files = Array.from(e.dataTransfer.files ?? []);
        if (files.length) onFiles(files);
      }}
    >
      {children}
      <div
        ref={overlayRef}
        className="chat-drop-overlay pointer-events-none absolute inset-0 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-[var(--color-accent)] bg-chat-main/80 opacity-0 transition-opacity"
        aria-hidden
      >
        <p className="text-sm font-medium text-[var(--color-accent)]">
          {disabledReason ?? "Drop files to attach"}
        </p>
      </div>
    </div>
  );
}
