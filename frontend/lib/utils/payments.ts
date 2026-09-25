const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });

export function formatAmount(amount: number, currency: string): string {
  if (currency === 'INR') return inr.format(amount);
  return `${currency} ${amount}`;
}

export function formatDateTime(iso: string): string {
  // The API sends naive UTC timestamps; mark them as UTC so they render in local time.
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** UPI UTRs are 12 digits; apps often display them with spaces. */
export function normalizeUtr(raw: string): string {
  return raw.replace(/\s+/g, '');
}

export const UTR_PATTERN = /^\d{12}$/;
export const MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024;
export const SCREENSHOT_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
