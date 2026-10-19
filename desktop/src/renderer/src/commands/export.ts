import { EXPORT_COMMANDS } from '../../../shared/commands'
import { settled } from '../state/project'
import type { CommandRegistry } from './registry'

export function registerExportCommands(registry: CommandRegistry): () => void {
  const disposers = [
    registry.register({
      id: EXPORT_COMMANDS.video,
      title: 'Export Video',
      category: 'Export',
      description: 'Render the finished video and save it as an MP4 on this Mac.',
      shortcut: 'Mod+E',
      // Exports leave the edit room; the person asks for them.
      aiCanRun: false,
      run: async () => {
        // The backend renders what it has saved, so the person's last edits go first.
        await settled()
        await window.clipnera.export.start()
      }
    }),
    registry.register({
      id: 'export.reveal',
      title: 'Show Exported Video in Finder',
      category: 'Export',
      description: 'Show the last exported video in Finder.',
      aiCanRun: false,
      run: () => window.clipnera.export.reveal()
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
