/** Shortcuts are written like "Mod+Shift+A": modifiers, then one key. Mod means ⌘ on macOS. */

export interface KeyLike {
  code: string
  key: string
  metaKey: boolean
  ctrlKey: boolean
  shiftKey: boolean
  altKey: boolean
}

interface Parsed {
  mod: boolean
  ctrl: boolean
  shift: boolean
  alt: boolean
  key: string
}

function parse(shortcut: string): Parsed {
  const parts = shortcut.split('+')
  const key = parts.pop() ?? ''
  return { mod: parts.includes('Mod'), ctrl: parts.includes('Ctrl'), shift: parts.includes('Shift'), alt: parts.includes('Alt'), key }
}

/** Compare by physical key for letters and digits, since ⌥ changes event.key ("⌥S" gives "ß"). */
function keyMatches(key: string, event: KeyLike): boolean {
  if (/^[A-Z]$/i.test(key)) return event.code === `Key${key.toUpperCase()}`
  if (/^[0-9]$/.test(key)) return event.code === `Digit${key}`
  // Named keys (Space, ArrowLeft, Escape…) match by code too: Space's event.key is " ".
  return event.code === key || event.key.toLowerCase() === key.toLowerCase()
}

export function matchesShortcut(shortcut: string, event: KeyLike): boolean {
  const s = parse(shortcut)
  return (
    s.mod === event.metaKey &&
    s.ctrl === event.ctrlKey &&
    s.shift === event.shiftKey &&
    s.alt === event.altKey &&
    keyMatches(s.key, event)
  )
}

export function hasModifier(shortcut: string): boolean {
  const s = parse(shortcut)
  return s.mod || s.ctrl || s.alt
}

/** macOS order: ⌃ ⌥ ⇧ ⌘ then the key. */
export function formatShortcut(shortcut: string): string {
  const s = parse(shortcut)
  const names: Record<string, string> = { Space: 'Space', ArrowLeft: '←', ArrowRight: '→', Escape: 'Esc' }
  return `${s.ctrl ? '⌃' : ''}${s.alt ? '⌥' : ''}${s.shift ? '⇧' : ''}${s.mod ? '⌘' : ''}${names[s.key] ?? s.key.toUpperCase()}`
}
