/**
 * Topic subscriptions and duplicate filtering. Pure, so node --test covers it.
 *
 * Topics: `*` (everything), a stream kind (`run`, `job`, `project`, `user`, or `run:*`) for every
 * stream of that kind, or an exact stream (`run:01J9…`).
 */
import type { RealtimeEvent, RealtimeHandler } from './events';

export function matchesTopic(topic: string, stream: string): boolean {
  if (topic === '*' || topic === stream) return true;
  const kind = topic.endsWith(':*') ? topic.slice(0, -2) : topic.includes(':') ? null : topic;
  return kind !== null && stream.startsWith(`${kind}:`);
}

/**
 * Drops redeliveries (reconnect overlap, two tabs) by `(stream, seq)` (events.md §7.2):
 * a durable event at or below the last durable seq, or an ephemeral one from an older state.
 * Events without a seq (`seq` 0, user-level streams) always pass; their handlers dedupe by id.
 * Gaps are the domain's job (the run store backfills from `/runs/{id}/events`).
 */
export function createDeduper() {
  const last = new Map<string, number>();
  return (event: RealtimeEvent): boolean => {
    if (event.seq <= 0) return true;
    const seen = last.get(event.stream);
    if (!event.durable) return seen === undefined || event.seq >= seen;
    if (seen !== undefined && event.seq <= seen) return false;
    last.set(event.stream, event.seq);
    return true;
  };
}

export function createRouter() {
  const subscribers = new Set<{ topic: string; handler: RealtimeHandler }>();
  const isNew = createDeduper();

  return {
    subscribe(topic: string, handler: RealtimeHandler): () => void {
      const entry = { topic, handler };
      subscribers.add(entry);
      return () => {
        subscribers.delete(entry);
      };
    },
    /** Delivers to every matching subscriber; one failing handler never stops the others. */
    dispatch(event: RealtimeEvent): void {
      if (!isNew(event)) return;
      for (const { topic, handler } of [...subscribers]) {
        if (!matchesTopic(topic, event.stream)) continue;
        try {
          handler(event);
        } catch (error) {
          console.error(`[realtime] handler for "${topic}" failed on ${event.type}`, error);
        }
      }
    },
  };
}
