/**
 * Mock run events for the replayable prompt run. Names and payload fields
 * follow docs/revamp/architecture/events.md §3–§6 (v1). Only the fields the
 * UI reads are typed; the real types are generated from the backend schema.
 * Positions here are seconds, not frames, to keep the sample readable.
 */

import type { PromptContext } from '@/components/ui/ContextChip';
import type { PromptMode } from '@/components/ui/PromptBar';

export type RunStatus =
  | 'queued'
  | 'acknowledged'
  | 'planning'
  | 'awaiting_input'
  | 'executing'
  | 'paused'
  | 'stopping'
  | 'checking'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'cancelled';

export interface Credits {
  estimate: number;
  held: number;
  spent: number;
}

export interface ErrorObject {
  code: string;
  message: string;
  retryable: boolean;
}

export interface Suggestion {
  label: string;
  prompt: string;
}

export type RunEvent =
  | { type: 'run.queued'; data: { queue_position: number; prompt_preview: string } }
  | { type: 'run.acknowledged'; data: { mode: PromptMode; chips: PromptContext[]; base_revision: number; credits: Credits } }
  | { type: 'run.plan.delta'; data: { text: string } }
  | {
      type: 'run.plan';
      data: { sentences: string[]; steps: { id: string; label: string }[]; credits: Credits; needs_approval: boolean };
    }
  | { type: 'run.message.delta'; data: { text: string; role: 'answer' | 'summary' } }
  | {
      type: 'run.question';
      data: { question_id: string; text: string; choices: { id: string; label: string; hint?: string }[]; allow_skip: true };
    }
  | { type: 'run.answered'; data: { question_id: string; choice_id?: string; skipped: boolean; by: 'user' | 'timeout' } }
  | { type: 'run.step.started'; data: { step_id: string; index: number; total: number; label: string } }
  | { type: 'run.step.progress'; data: { step_id: string; done?: number; total?: number; percent?: number; label?: string } }
  | { type: 'run.step.completed'; data: { step_id: string; label: string; summary: string; revisions: number[] } }
  | { type: 'run.step.failed'; data: { step_id: string; error: ErrorObject; will_retry: boolean; attempt: number } }
  | { type: 'run.lock.acquired'; data: { step_id: string; item_ids: string[] } }
  | { type: 'run.lock.released'; data: { step_id: string; item_ids: string[] } }
  | {
      type: 'run.operation.applied';
      data: { revision: number; base_revision: number; changed_ranges: [number, number][]; item_ids: string[]; step_id: string };
    }
  | { type: 'run.check.started'; data: Record<string, never> }
  | { type: 'run.check.completed'; data: { passed: boolean; findings: { severity: 'info' | 'warn'; text: string }[] } }
  | {
      type: 'run.paused';
      data: {
        reason: 'credits' | 'approval';
        credits: Credits;
        needed?: number;
        approval?: { kind: 'credits' | 'removal'; text: string; share_removed?: number };
        options: ('continue' | 'finish' | 'add_credits')[];
      };
    }
  | { type: 'run.resumed'; data: { reason: 'user_continue' | 'credits_added' | 'worker_restart' } }
  | { type: 'run.stop_requested'; data: { by: string } }
  | {
      type: 'run.result';
      data: {
        status: 'succeeded' | 'partial';
        version: { id: string; name: string; result_revision: number } | null;
        summary: { done: string[]; not_done: { text: string; reason: string }[] };
        answer?: string;
        plan_document?: { sentences: string[]; steps: { id: string; label: string }[] };
        suggestions: Suggestion[];
        credits: Credits;
        duration_ms: number;
      };
    }
  | {
      type: 'run.failed';
      data: { error: ErrorObject; version: { id: string; name: string } | null; suggestion?: Suggestion; credits: Credits };
    }
  | { type: 'run.cancelled'; data: { by: 'user' | 'system'; while: 'queued' | 'running' } }
  // Project, user and job streams the Editor also listens to.
  | { type: 'version.created'; data: { version_id: string; name: string } }
  | { type: 'credits.updated'; data: { balance: number } }
  | { type: 'sync.reset'; data: { reason: 'buffer_miss' | 'server_restart' } }
  | { type: 'job.succeeded'; data: { kind: 'run.render_full' } }
  // Client-local transport states (not server events): the stream dropped or came back.
  | { type: 'client.connection'; data: { online: boolean } };

export type RunEventType = RunEvent['type'];
