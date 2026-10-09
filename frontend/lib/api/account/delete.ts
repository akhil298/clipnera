import { apiFetch } from '../client';

import type { DeleteAccountRequest } from './types';

/**
 * `POST /me/delete` → `ApiResponse[None]`. Deletes the account, its files and its
 * connected social accounts. Fails with `CONFIRMATION_MISMATCH` (400) when the email
 * doesn't match; a failure leaves the account untouched.
 */
export const deleteAccount = (body: DeleteAccountRequest) =>
  apiFetch<null>('/me/delete', { method: 'POST', body, timeoutMs: 60_000 });
