import { useEffect, useState } from "react";

const DISMISS_KEY = "aqrem_unsaved_chat_notice_dismissed";

type Props = {
  visible: boolean;
};

export default function UnsavedChatNotice({ visible }: Props) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    try {
      setDismissed(sessionStorage.getItem(DISMISS_KEY) === "1");
    } catch {
      setDismissed(false);
    }
  }, []);

  if (!visible || dismissed) return null;

  return (
    <div
      className="mx-auto mb-3 flex max-w-3xl items-start gap-2 rounded-lg border border-amber-900/40 bg-amber-950/25 px-3 py-2 text-xs text-amber-100/90"
      role="status"
    >
      <span className="mt-0.5 shrink-0 text-amber-400/90" aria-hidden>
        ⓘ
      </span>
      <p className="flex-1 leading-relaxed">
        This conversation won&apos;t be saved after you close the session. Select or create a project to keep your chat
        history.
      </p>
      <button
        type="button"
        className="shrink-0 rounded px-1 text-amber-200/80 hover:text-amber-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-amber-400/60"
        aria-label="Dismiss notice"
        onClick={() => {
          try {
            sessionStorage.setItem(DISMISS_KEY, "1");
          } catch {
            /* ignore */
          }
          setDismissed(true);
        }}
      >
        ×
      </button>
    </div>
  );
}
