/** Parse an API timestamp. The API sends naive UTC timestamps; mark them as UTC
 * so they are not read as local time. */
export function parseApiDate(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function formatDate(iso: string): string {
  return parseApiDate(iso).toLocaleDateString(undefined, { dateStyle: 'medium' });
}

/** Format a calendar day the API sends as YYYY-MM-DD (a UTC day). */
export function formatDay(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { dateStyle: 'medium', timeZone: 'UTC' });
}

/** "just now", "5 min ago", "3 h ago", "yesterday", then a date. */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const date = parseApiDate(iso);
  const seconds = Math.round((now.getTime() - date.getTime()) / 1000);
  if (Number.isNaN(seconds)) return '';
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  return formatDate(iso);
}

/** A post time in the viewer's zone: "Today, 7:15 PM", "Tomorrow, 9:00 AM", "Tue 29 Sep, 6:00 PM". */
export function formatScheduleTime(iso: string, now: Date = new Date()): string {
  const date = parseApiDate(iso);
  const time = date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  const dayDiff = Math.round(
    (new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() -
      new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()) /
      86_400_000,
  );
  if (dayDiff === 0) return `Today, ${time}`;
  if (dayDiff === 1) return `Tomorrow, ${time}`;
  if (dayDiff === -1) return `Yesterday, ${time}`;
  const day = date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });
  return `${day}, ${time}`;
}
