'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useRef, useState } from 'react';

import { Button, Dialog, InlineAlert, Input } from '@/components/ui';
import { deleteAccount } from '@/lib/api/account/delete';
import { getEntitlements } from '@/lib/api/credits';
import { isApiError } from '@/lib/api/errors';
import type { UserProfile } from '@/lib/api/me';
import { ACCOUNT_DELETED_FLAG, accountMessage } from '@/lib/api/messages/account';
import { clearAuth } from '@/lib/auth';
import { useCopyToClipboard } from '@/lib/design/useCopyToClipboard';
import { creditKeys } from '@/lib/query/keys/credits';
import { parseApiDate } from '@/lib/utils/dates';

const DAY_MS = 86_400_000;
const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** What ends with the account, e.g. ["22 days of Pro left", "140 pack credits"]; each part only when above 0. */
function whatYouLose(me: UserProfile, packCredits: number): string[] {
  const daysLeft = me.plan !== 'free' && me.plan_expires_at ? Math.ceil((parseApiDate(me.plan_expires_at).getTime() - Date.now()) / DAY_MS) : 0;
  const plan = me.plan.charAt(0).toUpperCase() + me.plan.slice(1);
  return [
    daysLeft > 0 && `${plural(daysLeft, 'day', 'days')} of ${plan} left`,
    packCredits > 0 && plural(packCredits, 'pack credit', 'pack credits'),
  ].filter((part): part is string => Boolean(part));
}

interface DeleteAccountDialogProps {
  me: UserProfile;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Typed confirmation for `POST /me/delete`: the button unlocks when the account email
 * is typed (trimmed, any case, as the server checks). On success every local trace is
 * cleared and a full load lands on the home page, which shows the notice once.
 */
export function DeleteAccountDialog({ me, open, onOpenChange }: DeleteAccountDialogProps) {
  const queryClient = useQueryClient();
  const formId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [typed, setTyped] = useState('');
  const { state: copyState, copy } = useCopyToClipboard();

  const entitlements = useQuery({
    queryKey: creditKeys.entitlements(),
    queryFn: ({ signal }) => getEntitlements(signal),
    enabled: open,
  });

  const remove = useMutation({
    mutationFn: () => deleteAccount({ confirm_email: typed.trim() }),
    onSuccess: () => {
      clearAuth();
      queryClient.clear();
      try {
        sessionStorage.setItem(ACCOUNT_DELETED_FLAG, '1');
      } catch {
        // The notice is a courtesy; the account is gone either way.
      }
      window.location.replace('/');
    },
  });

  const matches = typed.trim().toLowerCase() === me.email.toLowerCase();
  const deleting = remove.isPending || remove.isSuccess;
  const failure = remove.isError ? accountMessage(remove.error, 'delete') : null;
  const requestId = remove.isError && isApiError(remove.error) ? remove.error.requestId : null;
  const loss = whatYouLose(me, entitlements.data?.purchased_credits_remaining ?? 0);

  const setOpen = (next: boolean) => {
    if (deleting) return;
    if (!next) {
      setTyped('');
      remove.reset();
    }
    onOpenChange(next);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      role="alertdialog"
      dismissible={!deleting}
      initialFocusRef={inputRef}
      title="Delete your account?"
      description="Your account, videos, clips, reels, brand kits, payment records and connected social accounts are deleted immediately and permanently. Unused credits and any paid time left are lost."
      footer={
        <>
          <Button variant="ghost" disabled={deleting} onClick={() => setOpen(false)}>
            Keep my account
          </Button>
          <Button type="submit" form={formId} variant="danger" disabled={!matches} loading={deleting} loadingLabel="Deleting">
            Permanently delete my account
          </Button>
        </>
      }
    >
      <form
        id={formId}
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (matches && !deleting) remove.mutate();
        }}
      >
        {loss.length > 0 && (
          <InlineAlert tone="warning" title={`You have ${loss.join(' and ')}.`}>
            {loss.length > 1 ? 'They end' : 'It ends'} with the account. Payments already made aren’t refunded.
          </InlineAlert>
        )}
        <Input
          ref={inputRef}
          label={
            <>
              Type <b className="break-all font-cn-mono font-semibold">{me.email}</b> to confirm
            </>
          }
          value={typed}
          onChange={(event) => {
            setTyped(event.target.value);
            if (remove.isError) remove.reset();
          }}
          type="email"
          inputMode="email"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          readOnly={deleting}
          error={failure ? `${failure.title}. ${failure.description}` : undefined}
        />
        {requestId && (
          <Button type="button" variant="ghost" size="sm" onClick={() => void copy(`Account deletion failed · request ${requestId}`)}>
            {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? `Request ${requestId}` : 'Copy details'}
          </Button>
        )}
      </form>
    </Dialog>
  );
}
