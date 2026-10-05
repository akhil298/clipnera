'use client';

import { CircleAlert, FileVideo, Link2 } from 'lucide-react';
import Link from 'next/link';
import type { RefObject } from 'react';

import { Button, FileDropzone, Input, Skeleton, VideoThumb, WorkingText, buttonClasses } from '@/components/ui';
import { VIDEO_CONTENT_TYPES } from '@/lib/upload/sourceVideo';
import { formatBytes, formatDuration } from '@/lib/utils/videoFile';

import type { NewVideo } from './useNewVideo';

const BILLING_HREF = '/dashboard/settings/billing';

/** A chosen video: poster or file tile, what it is, and Change. */
function ChosenSource({ poster, duration, title, detail, note, onChange }: {
  poster?: string;
  duration: number | null;
  title: string;
  detail: string;
  note: string;
  onChange: () => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
      <div className="w-24 shrink-0 sm:w-28">
        {poster ? (
          <VideoThumb poster={poster} aspect="16:9" duration={duration ?? undefined} />
        ) : (
          <div className="relative flex aspect-video items-center justify-center rounded-cn-md bg-cn-surface-active text-cn-fg-muted">
            <FileVideo aria-hidden className="size-5" />
            {duration !== null && (
              <span className="absolute bottom-1 right-1 rounded-cn-xs bg-cn-bg px-1 font-cn-mono text-cn-caption tabular-nums text-cn-fg">
                {formatDuration(duration)}
              </span>
            )}
          </div>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="line-clamp-2 text-cn-label font-semibold text-cn-fg">{title}</p>
        <p className="truncate text-cn-caption text-cn-fg-secondary">{detail}</p>
        <p className="text-cn-caption text-cn-fg-muted">{note}</p>
      </div>
      <Button size="sm" variant="ghost" onClick={onChange}>
        Change
      </Button>
    </div>
  );
}

/** The Video section: drop a file or paste a link, then the checked source with its length. */
export function SourceField({ form, linkRef }: { form: NewVideo; linkRef: RefObject<HTMLInputElement | null> }) {
  const { picked, youtube, youtubeUrl } = form;
  const maxMinutes = form.entitlements.data ? Math.floor(form.entitlements.data.max_upload_duration_seconds / 60) : null;
  const limitText = maxMinutes ? ` · up to ${maxMinutes >= 60 && maxMinutes % 60 === 0 ? `${maxMinutes / 60} hours` : `${maxMinutes} min`} on your plan` : '';

  let body;
  if (picked) {
    body = (
      <ChosenSource
        duration={picked.duration}
        title={picked.file.name}
        detail={formatBytes(picked.file.size)}
        note={picked.duration === null ? 'I’ll read its length once it’s uploaded' : 'Uploads from this tab, then continues on our side'}
        onChange={form.clearSource}
      />
    );
  } else if (form.reading || form.checking) {
    body = (
      <div className="flex items-center gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
        <Skeleton className="aspect-video w-24 shrink-0 sm:w-28" />
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <WorkingText className="text-cn-label">{form.reading ? 'Reading the video' : 'Checking the link'}</WorkingText>
          {form.checking && <span className="truncate font-cn-mono text-cn-caption text-cn-fg-muted">{youtubeUrl}</span>}
        </div>
      </div>
    );
  } else if (youtubeUrl && youtube.data) {
    const meta = youtube.data;
    body = (
      <ChosenSource
        poster={meta.thumbnail_url || undefined}
        duration={meta.duration_seconds || null}
        title={meta.title}
        detail={meta.channel_title}
        note={`Link checked · ${meta.resolution}`}
        onChange={form.clearSource}
      />
    );
  } else {
    body = (
      <div className="flex flex-col gap-3">
        {form.uploadsOn && (
          <FileDropzone
            title="Drop a video here"
            hint={`MP4, MOV, WebM or MKV${limitText}`}
            accept={VIDEO_CONTENT_TYPES.join(',')}
            maxSize={form.maxBytes}
            onFiles={([file]) => void form.pickFile(file)}
            onReject={() => form.setFileIssue('Use an MP4, MOV, WebM or MKV video.')}
            error={form.fileIssue}
          />
        )}
        <Input
          ref={linkRef}
          label={form.uploadsOn ? 'Or paste a YouTube link' : 'YouTube link'}
          leading={<Link2 />}
          type="url"
          inputMode="url"
          autoComplete="off"
          placeholder="youtube.com/watch?v=…"
          value={form.link}
          onChange={(event) => form.setLink(event.target.value)}
          error={form.linkIssue}
        />
      </div>
    );
  }

  return (
    <section aria-labelledby="new-video-source" className="flex flex-col gap-2">
      <h3 id="new-video-source" className="text-cn-label font-semibold text-cn-fg">
        Video
      </h3>
      {body}
      {form.tooLong && (
        <p role="alert" className="flex flex-wrap items-center gap-2 text-cn-label text-cn-danger-text">
          <CircleAlert aria-hidden className="size-4 shrink-0" />
          {form.tooLong}
          <Link href={BILLING_HREF} className={buttonClasses({ variant: 'ghost', size: 'sm' })}>
            See plans
          </Link>
        </p>
      )}
    </section>
  );
}
