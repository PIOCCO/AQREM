import { useEffect, useRef } from "react";
import { CopyButton } from "../ui/CopyButton";
import type { ActivityEvent } from "../../lib/activityApi";
import { formatActivityTime } from "../../lib/activityFormat";

type Props = {
  event: ActivityEvent | null;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
  hasPrev: boolean;
  hasNext: boolean;
};

export default function ActivityDetailDrawer({ event, onClose, onPrev, onNext, hasPrev, hasNext }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!event) return;
    closeRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown" && hasNext) {
        e.preventDefault();
        onNext();
      }
      if (e.key === "ArrowUp" && hasPrev) {
        e.preventDefault();
        onPrev();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [event, onClose, onNext, onPrev, hasNext, hasPrev]);

  if (!event) return null;

  const time = formatActivityTime(event.created_at);

  return (
    <>
      <button type="button" className="activity-drawer-backdrop lg:hidden" aria-label="Close details" onClick={onClose} />
      <aside className="activity-drawer" role="dialog" aria-modal="true" aria-labelledby="activity-drawer-title">
        <div className="activity-drawer-header">
          <h2 id="activity-drawer-title" className="text-base font-semibold text-[var(--color-text-primary)]">
            Event details
          </h2>
          <button ref={closeRef} type="button" className="activity-icon-btn" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="activity-drawer-body">
          <p className="text-[15px] leading-relaxed text-[var(--color-text-primary)]">{event.summary}</p>
          <p className="text-xs text-[var(--color-text-muted)] mt-1" title={time.title}>
            {time.absolute} · {time.title.split(",").pop()?.trim()}
          </p>

          <dl className="activity-drawer-dl">
            <div>
              <dt>Actor</dt>
              <dd>
                {event.actor_name}
                {event.actor_email ? ` · ${event.actor_email}` : ""}
              </dd>
            </div>
            {event.target_label ? (
              <div>
                <dt>Target</dt>
                <dd>{event.target_label}</dd>
              </div>
            ) : null}
            <div>
              <dt>Result</dt>
              <dd>{event.result}</dd>
            </div>
            <div>
              <dt>IP address</dt>
              <dd>{event.ip_address || "—"}</dd>
            </div>
            <div>
              <dt>Device / browser</dt>
              <dd className="break-all">{event.user_agent || "—"}</dd>
            </div>
            <div>
              <dt>Request ID</dt>
              <dd className="flex items-center gap-2">
                <span className="truncate font-mono text-xs">{event.request_id || "—"}</span>
                {event.request_id ? <CopyButton value={event.request_id} label="Copy request ID" /> : null}
              </dd>
            </div>
            <div>
              <dt>Event ID</dt>
              <dd className="flex items-center gap-2">
                <span className="truncate font-mono text-xs">{event.id}</span>
                <CopyButton value={event.id} label="Copy event ID" />
              </dd>
            </div>
          </dl>

          {event.changes ? (
            <section className="mt-4">
              <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">Changes</h3>
              <pre className="activity-changes-pre">{JSON.stringify(event.changes, null, 2)}</pre>
            </section>
          ) : null}
        </div>
        <div className="activity-drawer-footer">
          <button type="button" className="aq-btn-secondary" disabled={!hasPrev} onClick={onPrev}>
            Previous
          </button>
          <button type="button" className="aq-btn-secondary" disabled={!hasNext} onClick={onNext}>
            Next
          </button>
        </div>
      </aside>
    </>
  );
}
