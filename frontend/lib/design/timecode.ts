/**
 * Timecode formatting shared by TimeCode, VideoThumb, the player and the
 * markdown-lite renderer. Pure and import-free so `node --test` runs it directly.
 */

export interface TimecodeOptions {
  /** Always show hours (`0:01:05`). Default: only when the value or `total` reaches an hour. */
  hours?: boolean;
  /** Add frames at this rate (`1:05:12`). Omit for whole seconds. */
  fps?: number;
  /** Pads the minutes to match a longer total, so a column of times lines up. */
  total?: number;
}

const pad = (value: number): string => String(value).padStart(2, '0');

/** `65` → `1:05`; `3725` → `1:02:05`; with `fps: 30`, `65.5` → `1:05:15`. Negative values clamp to 0. */
export function formatTimecode(seconds: number, { hours, fps, total }: TimecodeOptions = {}): string {
  const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const whole = Math.floor(safe);
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  const showHours = hours ?? (h > 0 || (total ?? 0) >= 3600);
  const base = showHours ? `${h}:${pad(m)}:${pad(s)}` : `${(total ?? 0) >= 600 ? pad(m) : m}:${pad(s)}`;
  if (!fps) return base;
  const frames = Math.min(Math.floor((safe - whole) * fps), fps - 1);
  return `${base}:${pad(frames)}`;
}

/** `1:05` / `01:02:05` → seconds, or `null` when the text is not a timecode. */
export function parseTimecode(text: string): number | null {
  const match = /^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$/.exec(text.trim());
  if (!match) return null;
  const [, h, m, s] = match;
  if (Number(s) > 59 || (h !== undefined && Number(m) > 59)) return null;
  return Number(h ?? 0) * 3600 + Number(m) * 60 + Number(s);
}

/** For screen readers: `65` → "1 minute 5 seconds". */
export function spokenDuration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  const parts: Array<[number, string]> = [
    [Math.floor(whole / 3600), 'hour'],
    [Math.floor((whole % 3600) / 60), 'minute'],
    [whole % 60, 'second'],
  ];
  const words = parts.filter(([n]) => n > 0).map(([n, unit]) => `${n} ${unit}${n === 1 ? '' : 's'}`);
  return words.length > 0 ? words.join(' ') : '0 seconds';
}

/** ISO 8601 duration for `<time dateTime>`: `65.5` → `PT65.5S`. */
export function isoDuration(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds * 1000) / 1000);
  return `PT${safe}S`;
}
