import type { Player } from '../player/player'
import type { media as Media } from '../state/media'
import type { CommandRegistry } from './registry'

function seconds(value: unknown, name: string): number {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 0) return value
  throw new Error(`${name} must be a number of seconds`)
}

/** Viewer commands. All are safe for the AI: they only move the playhead or play. */
export function registerPlayerCommands(registry: CommandRegistry, player: Player, media: typeof Media): () => void {
  const base = { category: 'Playback', aiCanRun: true }

  // A file taken out of the library leaves the viewer too.
  const offMedia = media.subscribe(() => {
    const open = player.state.get().item
    if (open && !media.get().items.some((i) => i.id === open.id)) player.close()
  })

  const disposers = [
    registry.register<{ id: string }>({
      ...base,
      id: 'player.open',
      needsArgs: true,
      title: 'Open in Viewer',
      description: 'Show a media file in the viewer, by its id in the media library.',
      run: (args) => {
        const item = media.get().items.find((i) => i.id === args?.id)
        if (!item) throw new Error('No media file with that id')
        player.open(item)
      }
    }),
    registry.register({ ...base, id: 'player.togglePlay', title: 'Play / Pause', description: 'Play or pause the viewer.', shortcut: 'Space', run: () => player.toggle() }),
    registry.register({ ...base, id: 'player.play', title: 'Play', description: 'Play from the playhead at normal speed.', run: () => player.play() }),
    registry.register({ ...base, id: 'player.pause', title: 'Pause', description: 'Pause the viewer.', shortcut: 'K', run: () => player.pause() }),
    registry.register({ ...base, id: 'player.shuttleForward', title: 'Play Forward (faster each press)', description: 'Play forward; pressing again plays at 2× then 4×.', shortcut: 'L', run: () => player.shuttle(1) }),
    registry.register({ ...base, id: 'player.shuttleBack', title: 'Play Backward (faster each press)', description: 'Play backward; pressing again plays at 2× then 4×.', shortcut: 'J', run: () => player.shuttle(-1) }),
    registry.register({ ...base, id: 'player.stepForward', title: 'Next Frame', description: 'Pause and move one frame forward.', shortcut: 'ArrowRight', run: () => player.step(1) }),
    registry.register({ ...base, id: 'player.stepBack', title: 'Previous Frame', description: 'Pause and move one frame back.', shortcut: 'ArrowLeft', run: () => player.step(-1) }),
    registry.register<{ seconds: number }>({
      ...base,
      id: 'player.seek',
      needsArgs: true,
      title: 'Move Playhead',
      description: 'Move the playhead to a time in seconds.',
      run: (args) => player.seek(seconds(args?.seconds, 'seconds'))
    }),
    registry.register<{ from: number; to: number }>({
      ...base,
      id: 'player.playRange',
      needsArgs: true,
      title: 'Play Range',
      description: 'Play from one time to another (seconds), then stop. Use it to show the person a moment.',
      run: (args) => player.playRange(seconds(args?.from, 'from'), seconds(args?.to, 'to'))
    })
  ]

  return () => {
    offMedia()
    disposers.forEach((dispose) => dispose())
  }
}
