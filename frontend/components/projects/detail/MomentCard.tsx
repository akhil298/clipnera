'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CircleAlert, Copy, Download, MoreHorizontal, Scissors, Send, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button, buttonClasses } from '@/components/ui/Button';
import { Card, cardLinkOverlay } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { IconButton } from '@/components/ui/IconButton';
import { Menu, type MenuEntry } from '@/components/ui/Menu';
import { TimeCode } from '@/components/ui/TimeCode';
import { VideoThumb } from '@/components/ui/VideoThumb';
import { deleteClip, exportClip, type ProjectClip, type ProjectClipsResponse } from '@/lib/api/clips';
import { cx } from '@/lib/design/styles';
import { useCopyToClipboard } from '@/lib/design/useCopyToClipboard';
import { useHoverIntent } from '@/lib/design/useHoverIntent';
import { useFlag } from '@/lib/flags/useFlag';
import { clipKeys } from '@/lib/query/keys/clips';
import { downloadFile } from '@/lib/utils/clipExport';

import { durationOf, formatTagOf, isPlayable, quoteOf } from './moments';

export interface MomentCardProps {
  clip: ProjectClip;
  rank: number;
  /** Source length, for the position bar. */
  sourceSeconds: number;
  /** Tells the page what happened, for its one live region. */
  onNotice: (notice: { tone: 'success' | 'danger'; text: string }) => void;
}

const editHref = (clip: ProjectClip) =>
  `/dashboard/projects/${encodeURIComponent(clip.project_id)}/edit/${encodeURIComponent(clip.id)}`;

const fileName = (clip: ProjectClip, rank: number) =>
  `${(clip.title || `clip-${rank}`).replace(/[^\w\- ]+/g, '').trim().replace(/\s+/g, '-').toLowerCase() || `clip-${rank}`}.mp4`;

/** Where the moment sits in the source: a 4 px track, an amber tick at its start and a span for its length. */
function SourceBar({ start, length, total }: { start: number; length: number; total: number }) {
  if (total <= 0) return null;
  const left = Math.min(100, (start / total) * 100);
  const width = Math.max(0.5, Math.min(100 - left, (length / total) * 100));
  return (
    <span aria-hidden className="relative block h-1 w-full rounded-cn-full bg-cn-surface-active">
      <span className="absolute inset-y-0 rounded-cn-full bg-cn-accent/30" style={{ left: `${left}%`, width: `${width}%` }} />
      <span className="absolute -inset-y-0.5 w-0.5 rounded-cn-full bg-cn-accent" style={{ left: `${left}%` }} />
    </span>
  );
}

/**
 * A finished clip as a quote you can judge without pressing play
 * (07 §6.4): the spoken opening line, a typed format tag, where it sits in
 * the source, its length and score, and a muted preview on hover.
 */
export function MomentCard({ clip, rank, sourceSeconds, onNotice }: MomentCardProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const publishing = useFlag('social_publishing');
  const { copy } = useCopyToClipboard();
  const { active, handlers } = useHoverIntent();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const quote = quoteOf(clip);
  const format = formatTagOf(clip);
  const length = durationOf(clip);
  const playable = isPlayable(clip);
  const failed = clip.status === 'failed';
  const title = clip.title || `Clip ${rank}`;

  const download = useMutation({
    mutationFn: () => exportClip(clip),
    onSuccess: (url) => {
      downloadFile(url, fileName(clip, rank));
      onNotice({ tone: 'success', text: `“${title}” is downloading.` });
    },
    onError: () => onNotice({ tone: 'danger', text: `I couldn’t prepare “${title}” for download. The clip is safe; try again in a moment.` }),
  });

  const remove = useMutation({
    mutationFn: () => deleteClip(clip.id),
    onSuccess: () => {
      queryClient.setQueryData<ProjectClipsResponse>(clipKeys.list(clip.project_id), (data) =>
        data ? { ...data, clips: data.clips.filter((item) => item.id !== clip.id), total: data.total - 1 } : data,
      );
      onNotice({ tone: 'success', text: `Deleted “${title}”.` });
    },
    onError: () => onNotice({ tone: 'danger', text: `I couldn’t delete “${title}”. Nothing was removed.` }),
  });

  const menu: MenuEntry[] = [
    {
      id: 'copy',
      label: 'Copy the quote',
      icon: <Copy />,
      onSelect: () =>
        void copy(quote.text).then((ok) =>
          onNotice(ok ? { tone: 'success', text: 'Quote copied.' } : { tone: 'danger', text: 'Couldn’t copy. Select the quote and press ⌘C.' }),
        ),
    },
    ...(publishing
      ? [{ id: 'publish', label: 'Publish…', icon: <Send />, disabled: !playable, onSelect: () => router.push('/dashboard/scheduler') } satisfies MenuEntry]
      : []),
    { type: 'separator', id: 'sep' },
    { id: 'delete', label: 'Delete clip', icon: <Trash2 />, danger: true, onSelect: () => setConfirmDelete(true) },
  ];

  return (
    <Card padding="none" interactive className={cx('relative flex h-full flex-col overflow-hidden', remove.isPending && 'opacity-50')} {...handlers}>
      <VideoThumb
        poster={clip.poster_url ?? undefined}
        aspect="9:16"
        rounded="lg"
        duration={length}
        score={clip.score ?? undefined}
        previewSrc={playable ? (clip.presigned_url ?? undefined) : undefined}
        previewing={playable ? active : undefined}
        dimmed={failed}
        className={cx('m-2 mb-0', !playable && !failed && 'cn-pending-sheen')}
        topLeft={<span className="rounded-cn-xs bg-cn-bg/80 px-1.5 font-cn-mono text-cn-caption tabular-nums text-cn-fg">#{rank}</span>}
      />
      <div className="flex flex-1 flex-col gap-2 p-3">
        <Link href={editHref(clip)} className={cx('rounded-cn-xs text-cn-prose text-cn-fg', cardLinkOverlay)}>
          <q className="line-clamp-3">{quote.text}</q>
          <span className="sr-only">. {title}. Open in the editor.</span>
        </Link>
        {quote.spoken && clip.title && <p className="line-clamp-1 text-cn-caption text-cn-fg-muted">{clip.title}</p>}
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-cn-caption text-cn-fg-secondary">
          {format && <Badge>{format}</Badge>}
          <span className="inline-flex items-center gap-1">
            <span className="sr-only">From</span>
            <TimeCode seconds={clip.start_time} total={sourceSeconds} tone="inherit" />
          </span>
          <span aria-hidden>·</span>
          <TimeCode seconds={length} tone="inherit" />
        </p>
        <SourceBar start={clip.start_time} length={length} total={sourceSeconds} />
        {failed ? (
          <p className="flex items-center gap-1.5 text-cn-caption text-cn-danger-text">
            <CircleAlert aria-hidden className="size-4 shrink-0" />I couldn’t cut this clip.
          </p>
        ) : null}
        <div className="relative z-cn-raised mt-auto flex items-center gap-1 pt-1">
          <Link href={editHref(clip)} className={cx(buttonClasses({ variant: 'secondary', size: 'sm' }), 'flex-1')}>
            <Scissors aria-hidden className="size-4" />
            Edit
          </Link>
          <IconButton
            size="sm"
            label={playable ? `Download ${title}` : 'Not ready to download yet'}
            icon={<Download />}
            loading={download.isPending}
            disabled={!playable}
            onClick={() => download.mutate()}
          />
          <Menu trigger={(props) => <IconButton {...props} size="sm" label={`More for ${title}`} icon={<MoreHorizontal />} />} items={menu} align="end" />
        </div>
      </div>

      <Dialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        role="alertdialog"
        size="sm"
        title="Delete this clip?"
        description={`“${title}” and its edits are removed for good. The source video and the other clips stay.`}
        footer={
          <>
            <Button variant="secondary" data-autofocus onClick={() => setConfirmDelete(false)}>
              Keep it
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setConfirmDelete(false);
                remove.mutate();
              }}
            >
              Delete
            </Button>
          </>
        }
      />
    </Card>
  );
}
