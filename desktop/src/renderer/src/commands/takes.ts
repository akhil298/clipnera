import { edit, project, settled } from '../state/project'
import { takes } from '../state/takes'
import { batches, restoreOps } from '../timeline/takes'
import type { CommandRegistry } from './registry'

export async function saveTake(name: string, source: 'manual' | 'auto'): Promise<void> {
  await settled()
  takes.set({ list: await window.clipnera.project.saveTake(name, source) })
}

export function registerTakeCommands(registry: CommandRegistry): () => void {
  const base = { category: 'Takes', aiCanRun: false, needsArgs: true }
  const disposers = [
    registry.register<{ name: string }>({
      ...base,
      id: 'takes.save',
      title: 'Save as Take',
      description: 'Keep the edit as it is now, to compare with or go back to later.',
      run: (args) => saveTake(String(args?.name ?? ''), 'manual')
    }),
    registry.register<{ id: string }>({
      ...base,
      id: 'takes.restore',
      title: 'Restore Take',
      description: 'Put the timeline back the way it was in a take. Undo brings the current edit back.',
      run: async (args) => {
        const take = takes.get().list.find((t) => t.id === args?.id)
        const current = project.get().timeline
        if (!take || !current) throw new Error('That take is gone')
        // The current edit is kept as a take too, so restoring never loses work.
        await saveTake(`Before restoring “${take.name}”`, 'auto')
        for (const ops of batches(restoreOps(project.get().timeline ?? current, take.timeline))) await edit(ops)
      }
    }),
    registry.register<{ id: string }>({
      ...base,
      id: 'takes.remove',
      title: 'Delete Take',
      description: 'Delete a saved take.',
      run: async (args) => takes.set({ list: await window.clipnera.project.removeTake(String(args?.id ?? '')) })
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
