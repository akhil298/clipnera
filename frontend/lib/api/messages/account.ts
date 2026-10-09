import { isApiError } from '@/lib/api/errors';

/**
 * What Settings → Account says when a call fails (frontend.md §3.3: code → plain
 * sentence plus what is safe). Server `message` text is never shown. One file per domain.
 */

export interface UserMessage {
  title: string;
  description: string;
}

type Action = 'load' | 'delete';

const OFFLINE: UserMessage = { title: 'I couldn’t reach Clipnera', description: 'Check your connection and try again. Nothing was changed.' };
const SLOW: UserMessage = { title: 'Clipnera took too long to answer', description: 'Nothing was changed. Try again in a moment.' };

const BY_CODE: Partial<Record<string, Partial<Record<Action, UserMessage>>>> = {
  CONFIRMATION_MISMATCH: {
    delete: { title: 'That email doesn’t match this account', description: 'Type it exactly as shown above. Your account wasn’t deleted.' },
  },
  NETWORK: { load: OFFLINE, delete: { ...OFFLINE, description: 'Your account wasn’t deleted. Nothing was lost. Try again.' } },
  TIMEOUT: {
    load: SLOW,
    delete: { title: 'Deleting took too long to confirm', description: 'Reload this page: if you’re still signed in, your account wasn’t deleted and you can try again.' },
  },
};

const FALLBACK: Record<Action, UserMessage> = {
  load: { title: 'Your account details didn’t load', description: 'Nothing has changed. Settings you can’t see aren’t editable until they load.' },
  delete: { title: 'Your account wasn’t deleted', description: 'Nothing was lost. Try again.' },
};

/** The message for a failed account call. */
export function accountMessage(err: unknown, action: Action): UserMessage {
  if (!isApiError(err)) return FALLBACK[action];
  return BY_CODE[err.code]?.[action] ?? FALLBACK[action];
}

/** Session flag the landing page reads once after a deletion, then removes (request to Area 2). */
export const ACCOUNT_DELETED_FLAG = 'cn_account_deleted';
export const ACCOUNT_DELETED_NOTICE = 'Your account and its data have been deleted.';
