import { rules } from '../state/rules'
import type { CommandRegistry } from './registry'

/** Edit Rules are the person's own words: the AI follows them but can't change them. */
export function registerRuleCommands(registry: CommandRegistry): () => void {
  const base = { category: 'AI', aiCanRun: false, needsArgs: true }
  const save = async (list: string[]) => rules.set({ list: await window.clipnera.project.setRules(list) })
  const disposers = [
    registry.register<{ text: string }>({
      ...base,
      id: 'rules.add',
      title: 'Add Edit Rule',
      description: 'Add a rule the AI follows on every request in this project.',
      run: (args) => {
        const text = String(args?.text ?? '').trim()
        if (!text) throw new Error('Write the rule first')
        return save([...rules.get().list, text])
      }
    }),
    registry.register<{ index: number }>({
      ...base,
      id: 'rules.remove',
      title: 'Remove Edit Rule',
      description: 'Remove one of the Edit Rules.',
      run: (args) => save(rules.get().list.filter((_, i) => i !== Number(args?.index)))
    }),
    registry.register<{ key: string }>({
      ...base,
      id: 'rules.forget',
      title: 'Forget What the AI Learned',
      description: 'Make the AI forget one preference it learned from your corrections.',
      run: async (args) => rules.set({ learned: await window.clipnera.project.forgetStyle(String(args?.key ?? '')) })
    })
  ]
  return () => disposers.forEach((dispose) => dispose())
}
