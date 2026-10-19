import { describe, expect, it } from 'vitest'
import { formatShortcut, hasModifier, matchesShortcut, type KeyLike } from './keybindings'

const key = (overrides: Partial<KeyLike>): KeyLike => ({ code: '', key: '', metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...overrides })

describe('keybindings', () => {
  it('matches ⌘J and nothing looser or stricter', () => {
    expect(matchesShortcut('Mod+J', key({ code: 'KeyJ', key: 'j', metaKey: true }))).toBe(true)
    expect(matchesShortcut('Mod+J', key({ code: 'KeyJ', key: 'j' }))).toBe(false)
    expect(matchesShortcut('Mod+J', key({ code: 'KeyJ', key: 'J', metaKey: true, shiftKey: true }))).toBe(false)
  })

  it('matches by physical key when ⌥ changes the character', () => {
    expect(matchesShortcut('Mod+Alt+S', key({ code: 'KeyS', key: 'ß', metaKey: true, altKey: true }))).toBe(true)
  })

  it('matches named keys', () => {
    expect(matchesShortcut('Escape', key({ code: 'Escape', key: 'Escape' }))).toBe(true)
  })

  it('matches Space and arrows by physical key', () => {
    expect(matchesShortcut('Space', key({ code: 'Space', key: ' ' }))).toBe(true)
    expect(matchesShortcut('ArrowLeft', key({ code: 'ArrowLeft', key: 'ArrowLeft' }))).toBe(true)
    expect(matchesShortcut('Space', key({ code: 'Space', key: ' ', metaKey: true }))).toBe(false)
  })

  it('formats in macOS order', () => {
    expect(formatShortcut('Mod+Shift+A')).toBe('⇧⌘A')
    expect(formatShortcut('Mod+Alt+S')).toBe('⌥⌘S')
  })

  it('knows which shortcuts are safe while typing', () => {
    expect(hasModifier('Mod+J')).toBe(true)
    expect(hasModifier('Shift+J')).toBe(false)
    expect(hasModifier('Space')).toBe(false)
  })
})
