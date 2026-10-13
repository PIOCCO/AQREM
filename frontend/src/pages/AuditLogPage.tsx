import { useCallback, useEffect, useMemo, useState } from "react";
import ActivityDetailDrawer from "../components/activity/ActivityDetailDrawer";
import { FilterPopover } from "../components/activity/FilterPopover";
import WorkspacePage from "../components/layout/WorkspacePage";
import { IconRefresh, IconSearch } from "../components/icons/Icons";
import { EmptyState, ErrorState, PageHeader, SkeletonBlock } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { Tooltip } from "../components/ui/Tooltip";
import { ACTIVITY_ACTION_GROUPS } from "../lib/activityActions";
import {
  exportActivity,
  fetchActivity,
  fetchActivityActors,
  type ActivityActor,
  type ActivityEvent,
  type ActivityQuery,
} from "../lib/activityApi";
import { activityDayLabel, formatActivityTime, initialsFromName } from "../lib/activityFormat";
import { useProjectContext } from "../lib/projectContext";

const PAGE = 50;

type DatePreset = "24h" | "7d" | "30d" | "90d" | "custom" | null;

function presetRange(preset: DatePreset): { from?: string; to?: string } {
  if (!preset || preset === "custom") return {};
  const now = new Date();
  const to = now.toISOString();
  const ms =
    preset === "24h"
      ? 86400000
      : preset === "7d"
        ? 7 * 86400000
        : preset === "30d"
          ? 30 * 86400000
          : 90 * 86400000;
  return { from: new Date(now.getTime() - ms).toISOString(), to };
}

export default function AuditLogPage() {
  const { session } = useProjectContext();
  const toast = useToast();

  const [items, setItems] = useState<ActivityEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [actors, setActors] = useState<ActivityActor[]>([]);

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedActions, setSelectedActions] = useState<string[]>([]);
  const [selectedActors, setSelectedActors] = useState<string[]>([]);
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [datePreset, setDatePreset] = useState<DatePreset>(null);
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const [openFilter, setOpenFilter] = useState<"action" | "actor" | "date" | "sort" | "export" | null>(null);
  const [actionSearch, setActionSearch] = useState("");
  const [actorSearch, setActorSearch] = useState("");

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusedIndex, setFocusedIndex] = useState(0);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(t);
  }, [search]);

  const query = useMemo((): ActivityQuery => {
    const range =
      datePreset === "custom"
        ? {
            date_from: customFrom ? new Date(customFrom).toISOString() : undefined,
            date_to: customTo ? new Date(`${customTo}T23:59:59`).toISOString() : undefined,
          }
        : presetRange(datePreset);
    return {
      limit: PAGE,
      search: debouncedSearch || undefined,
      actions: selectedActions.length ? selectedActions : undefined,
      actor_user_id: selectedActors.length ? selectedActors : undefined,
      sort,
      ...range,
    };
  }, [debouncedSearch, selectedActions, selectedActors, sort, datePreset, customFrom, customTo]);

  const load = useCallback(
    async (append = false, offset = 0) => {
      if (!session) return;
      if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const data = await fetchActivity(session, { ...query, offset });
        setTotal(data.total);
        setNextOffset(data.next_offset ?? null);
        setItems((prev) => (append ? [...prev, ...data.items] : data.items));
        setError(null);
        setRequestId(null);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed to load activity";
        setError(msg);
        setRequestId(crypto.randomUUID());
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [session, query],
  );

  useEffect(() => {
    load(false, 0);
  }, [load]);

  useEffect(() => {
    if (!session) return;
    fetchActivityActors(session).then(setActors).catch(() => setActors([]));
  }, [session?.organizationId, session?.token]);

  const chips = useMemo(() => {
    const list: { key: string; label: string; clear: () => void }[] = [];
    selectedActions.forEach((a) =>
      list.push({
        key: `a-${a}`,
        label: a.replaceAll("_", " "),
        clear: () => setSelectedActions((prev) => prev.filter((x) => x !== a)),
      }),
    );
    selectedActors.forEach((id) => {
      const actor = actors.find((a) => a.user_id === id);
      list.push({
        key: `u-${id}`,
        label: actor?.name ?? "Actor",
        clear: () => setSelectedActors((prev) => prev.filter((x) => x !== id)),
      });
    });
    if (datePreset) {
      list.push({
        key: "date",
        label:
          datePreset === "custom"
            ? `Custom${customFrom ? ` from ${customFrom}` : ""}${customTo ? ` to ${customTo}` : ""}`
            : { "24h": "Last 24 hours", "7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days" }[
                datePreset
              ] ?? "Date",
        clear: () => {
          setDatePreset(null);
          setCustomFrom("");
          setCustomTo("");
        },
      });
    }
    if (debouncedSearch) {
      list.push({ key: "q", label: `Search: ${debouncedSearch}`, clear: () => setSearch("") });
    }
    return list;
  }, [selectedActions, selectedActors, actors, datePreset, customFrom, customTo, debouncedSearch]);

  const grouped = useMemo(() => {
    const map = new Map<string, ActivityEvent[]>();
    for (const item of items) {
      const label = activityDayLabel(item.created_at);
      if (!map.has(label)) map.set(label, []);
      map.get(label)!.push(item);
    }
    return Array.from(map.entries());
  }, [items]);

  const selectedEvent = items.find((i) => i.id === selectedId) ?? null;
  const selectedIndex = items.findIndex((i) => i.id === selectedId);

  async function onExport(format: "csv" | "json") {
    if (!session) return;
    setExporting(true);
    try {
      const blob = await exportActivity(session, format, query);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `activity-export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.push(`Exported activity as ${format.toUpperCase()}`);
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
      setOpenFilter(null);
    }
  }

  function clearAllFilters() {
    setSearch("");
    setSelectedActions([]);
    setSelectedActors([]);
    setDatePreset(null);
    setCustomFrom("");
    setCustomTo("");
  }

  const hasFilters = chips.length > 0;
  const emptyAll = !loading && !error && total === 0 && !hasFilters;
  const emptyFiltered = !loading && !error && total === 0 && hasFilters;

  return (
    <WorkspacePage className="workspace-page-activity">
      <PageHeader
        title="Activity"
        hideTitle={false}
        subtitle="A record of changes in your organization. Secrets and document contents are never logged."
        actions={
          <>
            <div className="relative">
              <button
                type="button"
                className="aq-btn-secondary activity-toolbar-btn"
                aria-haspopup="menu"
                aria-expanded={openFilter === "export"}
                disabled={exporting}
                onClick={() => setOpenFilter(openFilter === "export" ? null : "export")}
              >
                {exporting ? "Exporting…" : "Export"}
              </button>
              {openFilter === "export" ? (
                <div className="aq-dropdown">
                  <button type="button" className="aq-dropdown-item" onClick={() => void onExport("csv")}>
                    CSV
                  </button>
                  <button type="button" className="aq-dropdown-item" onClick={() => void onExport("json")}>
                    JSON
                  </button>
                </div>
              ) : null}
            </div>
            <Tooltip label="Refresh">
              <button
                type="button"
                className="activity-icon-btn"
                aria-label="Refresh activity"
                onClick={() => load(false, 0)}
              >
                <IconRefresh className="h-4 w-4" />
              </button>
            </Tooltip>
          </>
        }
      />

      <div className="activity-toolbar">
        <div className="activity-toolbar-search">
          <IconSearch className="activity-toolbar-search-icon" aria-hidden />
          <input
            className="activity-control"
            placeholder="Search activity"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search activity"
          />
        </div>
        <div className="relative">
          <button
            type="button"
            className="activity-control activity-filter-trigger"
            aria-expanded={openFilter === "action"}
            onClick={() => setOpenFilter(openFilter === "action" ? null : "action")}
          >
            Action
          </button>
          <FilterPopover open={openFilter === "action"} onClose={() => setOpenFilter(null)} label="Filter by action">
            <input
              className="activity-control mx-2 mb-2"
              placeholder="Search actions"
              value={actionSearch}
              onChange={(e) => setActionSearch(e.target.value)}
            />
            <div className="max-h-64 overflow-y-auto px-2">
              {ACTIVITY_ACTION_GROUPS.map((group) => {
                const actions = group.actions.filter((a) => a.includes(actionSearch.trim().toLowerCase()));
                if (!actions.length) return null;
                return (
                  <div key={group.label} className="mb-2">
                    <p className="text-xs font-medium text-[var(--color-text-muted)] px-1 py-1">{group.label}</p>
                    {actions.map((action) => (
                      <label key={action} className="flex items-center gap-2 px-1 py-1 text-sm cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedActions.includes(action)}
                          onChange={() =>
                            setSelectedActions((prev) =>
                              prev.includes(action) ? prev.filter((a) => a !== action) : [...prev, action],
                            )
                          }
                        />
                        <span className="capitalize">{action.replaceAll("_", " ")}</span>
                      </label>
                    ))}
                  </div>
                );
              })}
            </div>
          </FilterPopover>
        </div>
        <div className="relative">
          <button
            type="button"
            className="activity-control activity-filter-trigger"
            aria-expanded={openFilter === "actor"}
            onClick={() => setOpenFilter(openFilter === "actor" ? null : "actor")}
          >
            Actor
          </button>
          <FilterPopover open={openFilter === "actor"} onClose={() => setOpenFilter(null)} label="Filter by actor">
            <input
              className="activity-control mx-2 mb-2"
              placeholder="Search people"
              value={actorSearch}
              onChange={(e) => setActorSearch(e.target.value)}
            />
            <div className="max-h-64 overflow-y-auto px-2">
              {actors
                .filter(
                  (a) =>
                    a.name.toLowerCase().includes(actorSearch.toLowerCase()) ||
                    a.email.toLowerCase().includes(actorSearch.toLowerCase()),
                )
                .map((actor) => (
                  <label key={actor.user_id} className="flex items-center gap-2 px-1 py-1 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedActors.includes(actor.user_id)}
                      onChange={() =>
                        setSelectedActors((prev) =>
                          prev.includes(actor.user_id)
                            ? prev.filter((id) => id !== actor.user_id)
                            : [...prev, actor.user_id],
                        )
                      }
                    />
                    <span>
                      {actor.name} <span className="text-[var(--color-text-muted)]">({actor.email})</span>
                    </span>
                  </label>
                ))}
            </div>
          </FilterPopover>
        </div>
        <div className="relative">
          <button
            type="button"
            className="activity-control activity-filter-trigger"
            aria-expanded={openFilter === "date"}
            onClick={() => setOpenFilter(openFilter === "date" ? null : "date")}
          >
            Date
          </button>
          <FilterPopover open={openFilter === "date"} onClose={() => setOpenFilter(null)} label="Filter by date" widthClass="w-80">
            {(["24h", "7d", "30d", "90d"] as const).map((p) => (
              <button
                key={p}
                type="button"
                className="aq-dropdown-item"
                onClick={() => {
                  setDatePreset(p);
                  setOpenFilter(null);
                }}
              >
                {{ "24h": "Last 24 hours", "7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days" }[p]}
              </button>
            ))}
            <div className="border-t border-border px-3 py-2 space-y-2">
              <p className="text-xs text-[var(--color-text-muted)]">Custom range (YYYY-MM-DD)</p>
              <label className="block text-xs">
                From
                <input className="activity-control mt-1 w-full" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} />
              </label>
              <label className="block text-xs">
                To
                <input className="activity-control mt-1 w-full" value={customTo} onChange={(e) => setCustomTo(e.target.value)} />
              </label>
              <button
                type="button"
                className="aq-btn-secondary w-full"
                onClick={() => {
                  setDatePreset("custom");
                  setOpenFilter(null);
                }}
              >
                Apply range
              </button>
            </div>
          </FilterPopover>
        </div>
        <div className="relative">
          <button
            type="button"
            className="activity-control activity-filter-trigger"
            aria-expanded={openFilter === "sort"}
            onClick={() => setOpenFilter(openFilter === "sort" ? null : "sort")}
          >
            Sort
          </button>
          {openFilter === "sort" ? (
            <div className="aq-dropdown">
              <button type="button" className="aq-dropdown-item" onClick={() => { setSort("newest"); setOpenFilter(null); }}>
                Newest first
              </button>
              <button type="button" className="aq-dropdown-item" onClick={() => { setSort("oldest"); setOpenFilter(null); }}>
                Oldest first
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="activity-chip-row">
        <div className="flex flex-wrap gap-2 min-w-0">
          {chips.map((c) => (
            <button key={c.key} type="button" className="activity-chip" onClick={c.clear}>
              {c.label} <span aria-hidden>×</span>
            </button>
          ))}
          {hasFilters ? (
            <button type="button" className="activity-clear-link" onClick={clearAllFilters}>
              Clear all
            </button>
          ) : null}
        </div>
        <p className="activity-count" aria-live="polite">
          Showing {total} event{total === 1 ? "" : "s"}
        </p>
      </div>

      {loading ? (
        <div className="activity-list" aria-busy="true">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonBlock key={i} className="activity-skeleton-row" />
          ))}
        </div>
      ) : null}

      {error ? (
        <div className="aq-alert-error" role="alert">
          <p>{error}</p>
          {requestId ? <p className="text-xs mt-1 font-mono">Request ID: {requestId}</p> : null}
          <button type="button" className="aq-btn-secondary mt-3" onClick={() => load(false, 0)}>
            Retry
          </button>
        </div>
      ) : null}

      {emptyAll ? (
        <EmptyState
          title="No activity yet"
          description="When people invite teammates, connect sources, or change settings, those events will show up here."
        />
      ) : null}

      {emptyFiltered ? (
        <EmptyState
          title="No activity matches these filters"
          description="Try widening the date range or removing filters."
          action={
            <button type="button" className="aq-btn-secondary" onClick={clearAllFilters}>
              Clear filters
            </button>
          }
        />
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <div className="activity-list" role="list">
          {grouped.map(([day, rows]) => (
            <section key={day}>
              <h3 className="activity-day-header">{day}</h3>
              {rows.map((item, idxInGroup) => {
                const globalIndex = items.findIndex((x) => x.id === item.id);
                const time = formatActivityTime(item.created_at);
                const active = selectedId === item.id;
                return (
                  <div key={item.id} role="listitem">
                    <button
                      type="button"
                      className={`activity-row ${active ? "activity-row-active" : ""}`}
                      aria-expanded={active}
                      onClick={() => {
                        setSelectedId(item.id);
                        setFocusedIndex(globalIndex);
                      }}
                      onFocus={() => setFocusedIndex(globalIndex)}
                    >
                      <span className="activity-avatar" aria-hidden>
                        {item.actor_name === "System" ? "⚙" : initialsFromName(item.actor_name)}
                      </span>
                      <span className="activity-row-main min-w-0">
                        <span className="activity-summary">{item.summary}</span>
                        <span className="activity-secondary">{item.secondary}</span>
                      </span>
                      <span className="activity-row-meta">
                        {(item.is_failure || item.is_security) && (
                          <span
                            className={`activity-status-dot ${item.is_failure ? "activity-status-failed" : "activity-status-security"}`}
                            aria-label={item.is_failure ? "Failed" : "Security-sensitive"}
                          />
                        )}
                        <Tooltip label={time.title}>
                          <time dateTime={item.created_at} className="activity-time">
                            {time.relative}
                          </time>
                        </Tooltip>
                      </span>
                    </button>
                  </div>
                );
              })}
            </section>
          ))}
        </div>
      ) : null}

      {nextOffset != null && !loading ? (
        <button type="button" className="aq-btn-secondary mt-4 w-full" disabled={loadingMore} onClick={() => load(true, nextOffset)}>
          {loadingMore ? "Loading…" : "Load more"}
        </button>
      ) : null}

      <ActivityDetailDrawer
        event={selectedEvent}
        onClose={() => setSelectedId(null)}
        onPrev={() => {
          const next = items[selectedIndex - 1];
          if (next) setSelectedId(next.id);
        }}
        onNext={() => {
          const next = items[selectedIndex + 1];
          if (next) setSelectedId(next.id);
        }}
        hasPrev={selectedIndex > 0}
        hasNext={selectedIndex >= 0 && selectedIndex < items.length - 1}
      />
    </WorkspacePage>
  );
}
