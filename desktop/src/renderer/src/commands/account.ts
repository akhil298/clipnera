import type { CommandRegistry } from './registry'

/** Account commands. The AI can't run them: signing in and out is the person's call. */
export function registerAccountCommands(registry: CommandRegistry): () => void {
  return registry.register({
    id: 'account.signOut',
    title: 'Sign Out',
    category: 'Account',
    description: 'Sign out of Clipnera on this Mac.',
    aiCanRun: false,
    run: () => window.clipnera.auth.signOut()
  })
}
