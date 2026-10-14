import { useEffect, useState } from "react";
import { copyToClipboard } from "../../lib/copyToClipboard";
import { displayInviteUrl } from "../../lib/inviteLinks";

type Props = {
  url: string;
  title?: string;
};

export function InviteUrlSuccess({ url, title = "Invitation created" }: Props) {
  const [copied, setCopied] = useState(false);
  const href = displayInviteUrl(url);

  useEffect(() => {
    if (!copied) return;
    const t = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(t);
  }, [copied]);

  if (!href) return null;

  return (
    <div
      className="text-sm text-[var(--admin-status-active-text)] bg-[var(--admin-status-active-bg)] rounded px-3 py-3 space-y-2"
      role="status"
    >
      <p className="font-medium">{title}</p>
      <p className="text-xs opacity-90">Share this link securely (full URL).</p>
      <div className="flex flex-col sm:flex-row gap-2 sm:items-stretch">
        <input
          type="text"
          readOnly
          value={href}
          className="admin-input flex-1 min-w-0 break-all text-[var(--admin-status-active-text)] min-h-10"
          aria-label="Invitation link"
          onFocus={(e) => e.currentTarget.select()}
        />
        <div className="flex flex-wrap gap-2 shrink-0">
          <button
            type="button"
            className="admin-btn-primary sm:min-w-[7rem]"
            onClick={() => {
              void copyToClipboard(href).then((r) => {
                if (r.ok) setCopied(true);
              });
            }}
          >
            {copied ? "Copied!" : "Copy link"}
          </button>
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="admin-btn-secondary inline-flex items-center justify-center sm:min-w-[7rem] min-h-10 px-4"
          >
            Open link
          </a>
        </div>
      </div>
    </div>
  );
}
