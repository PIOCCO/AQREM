import { useState } from "react";
import { IconCopy } from "../icons/Icons";
import { Tooltip } from "./Tooltip";

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  return (
    <Tooltip label={copied ? "Copied" : label}>
      <button
        type="button"
        className="ref-msg-action-btn"
        onClick={() => void copy()}
        aria-label={copied ? "Copied" : label}
      >
        <IconCopy className="h-4 w-4" />
        {copied ? <span className="text-xs">Copied</span> : null}
      </button>
    </Tooltip>
  );
}
