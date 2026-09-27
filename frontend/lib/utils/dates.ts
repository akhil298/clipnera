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
