import type { Player } from '../player/player'
import { chat } from '../state/chat'
import { reason } from '../state/errors'
import { settled } from '../state/project'
import { sendPrompt } from './agent'
import type { CommandRegistry } from './registry'

/**
 * Answers outside agents (Claude Code, Codex over MCP). They get exactly what the in-app AI
 * gets: the commands it may run, through the same registry, logged under their own name.
 */
export function connectExternalAgents(registry: CommandRegistry, player: Player): () => void {
  return window.clipnera.mcp.onRequest(async (request) => {
    const respond = (result: unknown) => void window.clipnera.mcp.respond(request.id, { ok: true, result })
    try {
      if (request.kind === 'commands') {
        return respond(registry.list().filter((c) => c.aiCanRun).map((c) => ({ id: c.id, title: c.title, does: c.description, needsArgs: c.needsArgs === true, category: c.category })))
      }
      if (request.kind === 'run') {
        await registry.execute(request.command, request.args, 'external', request.client)
        await settled()
        return respond({ done: true })
      }
      await sendPrompt(request.prompt, player, request.client)
      const turn = chat.get().turns.at(-1)
      return respond({
        reply: turn?.text.join('\n\n') ?? '',
        edits: turn?.edits.map((e) => e.label) ?? [],
        plan: turn?.plan ? { title: turn.plan.title, status: turn.plan.status, summary: turn.plan.summary, note: turn.plan.status === 'proposed' ? 'Waiting for the person to approve it in Clipnera Studio.' : undefined } : null,
        note: turn?.note ?? null
      })
    } catch (error) {
      void window.clipnera.mcp.respond(request.id, { ok: false, error: reason(error) })
    }
  })
}
