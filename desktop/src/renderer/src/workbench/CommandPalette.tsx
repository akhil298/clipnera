import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { commands, runCommand } from '../commands'
import { formatShortcut } from '../commands/keybindings'
import { search } from '../commands/palette'
import { palette } from '../state/palette'
import { useStore } from '../state/store'

const LIMIT = 12

export function CommandPalette() {
  const open = useStore(palette, (s) => s.open)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setActive(0)
    input.current?.focus()
  }, [open])

  if (!open) return null
  const results = search(commands.list(), query).slice(0, LIMIT)
  // Anything typed can also go straight to the AI.
  const ask = query.trim() ? { id: '__ask', title: `Ask the AI: “${query.trim()}”`, category: 'AI', aiCanRun: false, shortcut: undefined } : null
  const options = ask ? [...results, ask] : results
  const close = () => palette.set({ open: false })
  const choose = (id: string | undefined) => {
    close()
    if (id === '__ask') runCommand('agent.send', { prompt: query.trim() })
    else if (id) runCommand(id)
  }

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') close()
    else if (event.key === 'ArrowDown') setActive((i) => Math.min(i + 1, options.length - 1))
    else if (event.key === 'ArrowUp') setActive((i) => Math.max(i - 1, 0))
    else if (event.key === 'Enter') choose(options[active]?.id)
    else return
    event.preventDefault()
    event.stopPropagation()
  }

  return (
    <div className="palette-backdrop" onPointerDown={close}>
      <div className="palette" role="dialog" aria-label="Command palette" onPointerDown={(e) => e.stopPropagation()}>
        <input
          ref={input}
          id="palette-input"
          role="combobox"
          aria-expanded="true"
          aria-controls="palette-results"
          aria-activedescendant={options[active] ? `palette-${options[active].id}` : undefined}
          placeholder="Type a command…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setActive(0)
          }}
          onKeyDown={onKeyDown}
        />
        <ul id="palette-results" role="listbox" aria-label="Commands">
          {options.map((c, i) => (
            <li
              key={c.id}
              id={`palette-${c.id}`}
              role="option"
              aria-selected={i === active}
              onPointerEnter={() => setActive(i)}
              onClick={() => choose(c.id)}
            >
              <span className="palette-category">{c.category}</span>
              <span className="palette-title">{c.title}</span>
              {c.aiCanRun && <span className="palette-ai" title="The AI can run this">AI</span>}
              {c.shortcut && <kbd>{formatShortcut(c.shortcut)}</kbd>}
            </li>
          ))}
          {options.length === 0 && <li className="palette-none">Type a command, or anything to ask the AI</li>}
        </ul>
      </div>
    </div>
  )
}
