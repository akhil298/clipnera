/** Parse an API timestamp. The API sends naive UTC timestamps; mark them as UTC
 * so they are not read as local time. */
export function parseApiDate(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function formatDate(iso: string): string {
  return parseApiDate(iso).toLocaleDateString(undefined, { dateStyle: 'medium' });
}
