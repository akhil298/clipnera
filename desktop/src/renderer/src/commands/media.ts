import { MEDIA_COMMANDS } from '../../../shared/commands'
import type { LayoutState } from '../state/layout'
import type { Store } from '../state/store'
import type { CommandRegistry } from './registry'

function paths(value: unknown): string[] | undefined {
  if (value === undefined) return undefined
  if (Array.isArray(value) && value.every((p) => typeof p === 'string')) return value
  throw new Error('paths must be a list of file paths')
}

/**
 * Media commands. The AI can't run these yet: picking files is the person's call, and removing
 * gets AI access once removals can be undone (phase 5).
 */
export function registerMediaCommands(registry: CommandRegistry, layout: Store<LayoutState>): () => void {
  const showMedia = () => layout.set({ sideView: 'media', sideVisible: true })
  const disposers = [
    registry.register<{ paths?: string[] } | undefined>({
      id: MEDIA_COMMANDS.import,
      title: 'Import Media',
      category: 'Media',
      description: 'Add video or audio files to the project. With no paths, shows the file picker.',
      shortcut: 'Mod+I',
      aiCanRun: false,
      async run(args) {
        showMedia()
        const chosen = paths(args?.paths)
        await (chosen ? window.clipnera.media.import(chosen) : window.clipnera.media.pick())
      }
    }),
    registry.register<{ id: string }>({
      id: 'media.remove',
      needsArgs: true,
      title: 'Remove from Project',
      category: 'Media',
      description: 'Take a file out of the project. The original file on disk is not touched.',
      aiCanRun: false,
      run: (args) => {
        if (typeof args?.id !== 'string') throw new Error('id is required')
        return window.clipnera.media.remove(args.id)
      }
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
