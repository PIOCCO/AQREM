import { useEffect, useState } from "react";
import { copyToClipboard } from "../../lib/copyToClipboard";

type Props = {
  url: string;
  title?: string;
};

export function InviteUrlSuccess({ url, title = "Invitation created" }: Props) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const t = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(t);
  }, [copied]);

  return (
    <div
      className="text-sm text-[var(--admin-status-active-text)] bg-[var(--admin-status-active-bg)] rounded px-3 py-3 space-y-2"
      role="status"
    >
      <p className="font-medium">{title}</p>
      <p className="text-xs opacity-90">Share this link securely. It opens the invitation page in a new tab.</p>
      <div className="flex flex-col sm:flex-row gap-2 sm:items-stretch">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="admin-input flex-1 break-all text-[var(--admin-status-active-text)] underline-offset-2 hover:underline min-h-10 py-2"
        >
          {url}
        </a>
        <button
          type="button"
          className="admin-btn-primary shrink-0 sm:min-w-[7rem]"
          onClick={() => {
            void copyToClipboard(url).then((r) => {
              if (r.ok) setCopied(true);
            });
          }}
        >
          {copied ? "Copied!" : "Copy link"}
        </button>
      </div>
    </div>
  );
}
