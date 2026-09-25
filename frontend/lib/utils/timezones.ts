/** Times are stored in UTC and shown in the zone the user picks. */

export const DEFAULT_TIMEZONE = 'Asia/Kolkata';

function offsetMs(date: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((p) => p.type === type)?.value);
  const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'));
  return asUtc - date.getTime();
}

/** A <input type="datetime-local"> value ("2026-09-26T19:30") read as wall-clock time in `timeZone`. */
export function zonedLocalToUtc(local: string, timeZone: string): Date {
  const [datePart, timePart = '00:00'] = local.split('T');
  const [y, m, d] = datePart.split('-').map(Number);
  const [hh, mm] = timePart.split(':').map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  let utc = guess - offsetMs(new Date(guess), timeZone);
  // Re-check across a DST change between the guess and the answer.
  const corrected = guess - offsetMs(new Date(utc), timeZone);
  if (corrected !== utc) utc = corrected;
  return new Date(utc);
}

/** The datetime-local value for `date` as wall-clock time in `timeZone`. */
export function utcToZonedLocal(date: Date, timeZone: string): string {
  const shifted = new Date(date.getTime() + offsetMs(date, timeZone));
  return shifted.toISOString().slice(0, 16);
}

export function formatInZone(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(iso));
}
