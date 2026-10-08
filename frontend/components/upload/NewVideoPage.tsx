'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';

import { NewVideoBody, NewVideoFooter } from './NewVideoForm';
import { useNewVideo } from './useNewVideo';

/** New video on a direct load of /dashboard/upload: the same form as the dialog, as a page. */
export function NewVideoPage() {
  const router = useRouter();
  const linkRef = useRef<HTMLInputElement>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const form = useNewVideo((projectId) => router.push(`/dashboard/projects/${projectId}`));

  useEffect(() => {
    linkRef.current?.focus();
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8 sm:py-12">
      <header className="flex flex-col gap-1">
        <h1 className="font-cn-display text-cn-title-lg font-bold text-cn-fg">New video</h1>
        <p className="text-cn-body text-cn-fg-secondary">
          Check the video and the cost. I start once you confirm, and you can close the tab after any upload finishes.
        </p>
      </header>
      <div className="rounded-cn-xl border border-cn-border bg-cn-surface">
        <div className="p-4 sm:p-5">
          <NewVideoBody form={form} linkRef={linkRef} promptRef={promptRef} />
        </div>
        <div className="border-t border-cn-border p-4 sm:px-5">
          <NewVideoFooter form={form} onCancel={() => router.push('/dashboard')} />
        </div>
      </div>
    </div>
  );
}
