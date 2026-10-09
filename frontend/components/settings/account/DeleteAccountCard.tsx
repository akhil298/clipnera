'use client';

import { useState } from 'react';

import { Button } from '@/components/ui';
import type { UserProfile } from '@/lib/api/me';
import { cx, focusRing } from '@/lib/design/styles';

import { SettingsCard } from '../frame';

import { DeleteAccountDialog } from './DeleteAccountDialog';

/** Always the last card (07 §5.6). Copy kept word for word from the legacy AccountPrivacyPanel. */
export function DeleteAccountCard({ me }: { me: UserProfile }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <SettingsCard
        id="delete-account"
        danger
        title="Delete account"
        description={
          <>
            Permanently deletes your account, videos, clips, reels, brand kits, payment records and connected social accounts. Unused credits and any
            paid time left are lost. This cannot be undone. See the{' '}
            <a href="/privacy" className={cx('rounded-cn-xs text-cn-accent-text underline underline-offset-2', focusRing)}>
              privacy policy
            </a>
            .
          </>
        }
        actions={
          <Button variant="secondary" className="w-full text-cn-danger-text sm:w-auto" onClick={() => setOpen(true)}>
            Delete account…
          </Button>
        }
      />
      <DeleteAccountDialog me={me} open={open} onOpenChange={setOpen} />
    </>
  );
}
