function localeDateTime(d: Date, style: "medium" | "full"): string {
  try {
    if (style === "full") {
      return d.toLocaleString(undefined, { dateStyle: "full", timeStyle: "long", timeZoneName: "short" });
    }
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZoneName: "short" });
  } catch {
    return d.toLocaleString();
  }
}

export function formatActivityTime(iso: string, now = new Date()): { relative: string; absolute: string; title: string } {
  const d = new Date(iso);
  const absolute = localeDateTime(d, "medium");
  const title = localeDateTime(d, "full");
  const diffMs = now.getTime() - d.getTime();
  const diffDays = diffMs / 86400000;
  if (diffDays >= 7) {
    return {
      relative: d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }),
      absolute,
      title,
    };
  }
  const diffMin = Math.max(1, Math.round(diffMs / 60000));
  if (diffMin < 60) return { relative: `${diffMin} min ago`, absolute, title };
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 48) return { relative: `${diffHr} hr ago`, absolute, title };
  const diffD = Math.round(diffDays);
  return { relative: `${diffD} days ago`, absolute, title };
}

export function activityDayLabel(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startEvent = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = (startToday.getTime() - startEvent.getTime()) / 86400000;
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

export function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
  return (name[0] ?? "?").toUpperCase();
}
