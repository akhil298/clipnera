'use client';

import { Sparkles } from 'lucide-react';
import Link from 'next/link';
import type { RefObject } from 'react';

import { Button, InlineAlert, Input, Textarea, buttonClasses } from '@/components/ui';
import { isApiError } from '@/lib/api/errors';

import { ChannelIntroNudge } from './ChannelIntroNudge';
import { FolderField } from './FolderField';
import { RunOptionsField } from './RunOptionsField';
import { SourceField } from './SourceField';
import type { NewVideo } from './useNewVideo';

const BILLING_HREF = '/dashboard/settings/billing';
const credits = (n: number) => n.toLocaleString('en-IN');

function startErrorText(error: unknown): string {
  if (isApiError(error) && error.status !== 0 && error.status < 500) return `${error.message} Nothing was charged.`;
  return 'I couldn’t start this project. Nothing was charged. Try again in a moment.';
}

/** The form between the dialog's (or page's) header and footer. */
export function NewVideoBody({ form, linkRef, promptRef }: {
  form: NewVideo;
  linkRef: RefObject<HTMLInputElement | null>;
  promptRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const plan = form.entitlements.data;
  return (
    <div className="flex flex-col gap-5">
      <ChannelIntroNudge allowed={!!plan?.creator_intro} />
      <SourceField form={form} linkRef={linkRef} />

      <Textarea
        ref={promptRef}
        label="What should Clipnera make?"
        hint="Optional. Leave it empty and I pick the best moments."
        value={form.prompt}
        onChange={(event) => form.setPrompt(event.target.value)}
        minRows={2}
        maxRows={5}
        maxLength={500}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Project name"
          hint={form.hasSource ? 'Filled from the video; change it any time.' : 'Filled from the video once you add one.'}
          value={form.title}
          onChange={(event) => form.setTitle(event.target.value)}
          maxLength={500}
        />
        {form.folders.isSuccess && <FolderField folders={form.folders.data} value={form.folderId} onChange={form.setFolderId} />}
      </div>

      <RunOptionsField value={form.options} onChange={form.setOptions} plan={plan} brollAllowed={form.brollAllowed} />

      {form.picked && (
        <p className="text-cn-caption text-cn-fg-muted">Large files upload in parts. You can pause, and it picks up where it stopped if the connection drops.</p>
      )}

      {form.entitlements.isError && (
        <InlineAlert
          tone="danger"
          live="alert"
          action={
            <Button size="sm" variant="secondary" onClick={() => void form.entitlements.refetch()} loading={form.entitlements.isFetching}>
              Try again
            </Button>
          }
        >
          I couldn’t load your credits, so I can’t show the cost yet.
        </InlineAlert>
      )}
      {form.shortOfCredits && form.cost !== null && form.balance !== null && (
        <InlineAlert
          tone="danger"
          live="alert"
          action={
            <Link href={BILLING_HREF} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
              Add credits
            </Link>
          }
        >
          {`This video needs ${credits(form.cost)} credits; you have ${credits(form.balance)}. Pick fewer formats, or add credits and come back.`}
        </InlineAlert>
      )}
      {!form.online && (
        <InlineAlert tone="warning" live="status">
          You’re offline. Make clips works again when the connection is back.
        </InlineAlert>
      )}
      {form.start.isError && (
        <InlineAlert tone="danger" live="alert">
          {startErrorText(form.start.error)}
        </InlineAlert>
      )}
      {form.start.isPending && (
        <p role="status" className="text-cn-label text-cn-fg-secondary">
          Creating the project. I’ll take you to its progress page.
        </p>
      )}
    </div>
  );
}

/** Cost line, Cancel and the one amber action, which names the cost. */
export function NewVideoFooter({ form, onCancel }: { form: NewVideo; onCancel: () => void }) {
  const count = form.options.formats.length;
  const formats = `${count} format${count === 1 ? '' : 's'}`;
  const line = !form.hasSource
    ? 'Add a video to see the cost'
    : form.cost === null
      ? form.picked && form.picked.duration === null
        ? `${formats} · cost set once the video is read`
        : `${formats} · working out the cost`
      : form.shortOfCredits || form.balance === null
        ? formats
        : `${formats} · ${credits(form.balance - form.cost)} credits left after`;

  return (
    <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center">
      <p className="flex-1 text-cn-label text-cn-fg-secondary">{line}</p>
      <Button variant="ghost" className="hidden sm:inline-flex" onClick={onCancel} disabled={form.start.isPending}>
        Cancel
      </Button>
      <Button
        leadingIcon={<Sparkles />}
        onClick={form.submit}
        disabled={!form.canStart}
        loading={form.start.isPending}
        loadingLabel="Starting"
        fullWidth
        className="sm:w-auto"
      >
        {form.cost !== null && !form.shortOfCredits && !form.tooLong ? `Make clips · ${credits(form.cost)} credits` : 'Make clips'}
      </Button>
    </div>
  );
}
