'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useRef } from 'react';

import { Dialog } from '@/components/ui';

import { NewVideoBody, NewVideoFooter } from './NewVideoForm';
import { useNewVideo } from './useNewVideo';

const DESCRIPTION = 'Check the video and the cost. I start once you confirm, and you can close the tab after any upload finishes.';

/**
 * New video over the current page (intercepted /dashboard/upload). Escape,
 * the close button and Cancel go Back; starting routes to the project's
 * progress page, which closes the dialog because the path no longer matches.
 */
export function NewVideoDialog() {
  const router = useRouter();
  const pathname = usePathname();
  const linkRef = useRef<HTMLInputElement>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const form = useNewVideo((projectId) => router.push(`/dashboard/projects/${projectId}`));
  const open = pathname.endsWith('/dashboard/upload');
  const close = () => router.back();

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && close()}
      size="lg"
      title="New video"
      description={DESCRIPTION}
      dismissible={!form.start.isPending}
      initialFocusRef={form.hasSource ? promptRef : linkRef}
      footer={<NewVideoFooter form={form} onCancel={close} />}
    >
      <NewVideoBody form={form} linkRef={linkRef} promptRef={promptRef} />
    </Dialog>
  );
}
