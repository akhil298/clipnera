import { useEffect } from 'react'
import { commands, runCommand } from '.'
import { hasModifier, matchesShortcut } from './keybindings'

const NOT_TEXT = new Set(['range', 'checkbox', 'radio', 'button', 'submit', 'reset', 'color', 'file'])
// In a text box these keep their usual text-editing meaning.
const TEXT_EDITING = new Set(['Mod+Z', 'Shift+Mod+Z', 'Mod+A', 'Mod+C', 'Mod+V', 'Mod+X'])

/** Single-key shortcuts (Space, J/K/L, arrows) stand aside only while the person is typing text. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return true
  return target instanceof HTMLInputElement && !NOT_TEXT.has(target.type)
}

/** Routes keyboard shortcuts and native menu clicks to commands. */
export function useCommandInputs(): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const matching = commands.list().filter((c) => c.shortcut && matchesShortcut(c.shortcut, event))
      const command = matching.find((c) => c.when?.()) ?? matching.find((c) => !c.when)
      if (!command?.shortcut) return
      // Esc always reaches its command (it stops the AI); other single keys wait while typing.
      const blocked = command.shortcut !== 'Escape' && (!hasModifier(command.shortcut) || TEXT_EDITING.has(command.shortcut))
      if (blocked && isTyping(event.target)) return
      event.preventDefault()
      runCommand(command.id)
    }
    window.addEventListener('keydown', onKeyDown)
    const offMenu = window.clipnera.onRunCommand((id) => runCommand(id))
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      offMenu()
    }
  }, [])
}
