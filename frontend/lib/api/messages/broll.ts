import { isApiError } from '@/lib/api/errors';

/**
 * What the B-roll library says when a call fails (frontend.md §3.3: code → plain sentence plus
 * what is safe). Server `message` text is never shown. One file per domain.
 */

export interface UserMessage {
  title: string;
  description: string;
}

type Action = 'load' | 'detail' | 'favourite' | 'report' | 'collect' | 'createCollection';

const BY_CODE: Partial<Record<string, Partial<Record<Action, UserMessage>> & { any?: UserMessage }>> = {
  RATE_LIMITED: {
    report: { title: 'You’ve sent 10 reports today', description: 'Try again tomorrow. The reports you sent are with us.' },
    any: { title: 'That was a lot at once', description: 'Wait a few seconds, then try again.' },
  },
  LIMIT_REACHED: {
    collect: { title: 'That collection is full', description: 'Remove a shot from it, or add this one to another collection.' },
    createCollection: { title: 'You have the most collections your plan allows', description: 'Delete one, or see plans for more.' },
  },
  FEATURE_DISABLED: {
    any: { title: 'The library is paused for your account', description: 'Footage already in your projects keeps playing.' },
  },
  NETWORK: {
    any: { title: 'I couldn’t reach Clipnera', description: 'Check your connection and try again. Nothing was changed.' },
  },
  TIMEOUT: {
    any: { title: 'Clipnera took too long to answer', description: 'Nothing was changed. Try again in a moment.' },
  },
};

const NOT_FOUND: UserMessage = { title: 'This shot is no longer in the library', description: 'Shots you already used keep playing in your projects.' };

const FALLBACK: Record<Action, UserMessage> = {
  load: {
    title: 'The library didn’t load',
    description: 'Your projects and the footage in them are safe. Check your connection and try again.',
  },
  detail: { title: 'I couldn’t load this shot’s details', description: 'It’s still in the library. Try again in a moment.' },
  favourite: { title: 'I couldn’t update your favourites', description: 'Nothing changed. Try again in a moment.' },
  report: { title: 'Your report didn’t send', description: 'Nothing was lost; your choice is still here. Try again.' },
  collect: { title: 'I couldn’t add it to that collection', description: 'The collection is unchanged. Try again in a moment.' },
  createCollection: { title: 'I couldn’t create the collection', description: 'Nothing was created. Try again in a moment.' },
};

/** The message for a failed library call. */
export function brollMessage(err: unknown, action: Action): UserMessage {
  if (!isApiError(err)) return FALLBACK[action];
  if (err.status === 404 && (action === 'detail' || action === 'favourite' || action === 'report')) return NOT_FOUND;
  const byCode = BY_CODE[err.code];
  return byCode?.[action] ?? byCode?.any ?? FALLBACK[action];
}
