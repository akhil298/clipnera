/**
 * The readable part of an error. Errors from the main process arrive as
 * "Error invoking remote method 'x': Error: <reason>"; only the reason is for people.
 */
export function reason(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error)
  return text.replace(/^Error invoking remote method '[^']+': (?:\w*Error: )?/, '')
}
