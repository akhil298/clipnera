'use client';

/**
 * Stand-ins for design-system additions this wave needs but 02 does not yet
 * ship (listed in docs/revamp/screens/01-entry-and-dashboard.md, "Design-system
 * additions"). Each is token-only and deliberately minimal; the Design System
 * owner builds the real component. Do not import these outside the mockups.
 */

import { ChevronRight, FileVideo, Film, Folder, Youtube, X } from 'lucide-react';
import type { ReactNode } from 'react';

import { Badge } from '@/components/ui/Badge';
import { LogoMark } from '@/components/ui/LogoMark';
import { Popover } from '@/components/ui/Popover';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

/** DS-1 Wordmark: the one brand lock-up (mark + lowercase Syne), replacing four variants. */
export function Wordmark({ size = 'md', className }: { size?: 'sm' | 'md'; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-2', className)}>
      <LogoMark size={size === 'sm' ? 24 : 28} />
      <span className={cx('font-cn-display font-bold tracking-tight text-cn-fg', size === 'sm' ? 'text-cn-body-lg' : 'text-cn-title-sm')}>
        clipnera
      </span>
    </span>
  );
}

/** DS-2 Avatar (02 §3.23): initials on `surface-active`; workspaces are rounded squares. */
export function Avatar({ initials, size = 32, square = false }: { initials: string; size?: 24 | 32 | 40; square?: boolean }) {
  const box = size === 24 ? 'size-6 text-cn-caption' : size === 32 ? 'size-8 text-cn-caption' : 'size-10 text-cn-label';
  return (
    <span
      aria-hidden
      className={cx(
        'inline-flex shrink-0 items-center justify-center bg-cn-surface-active font-semibold text-cn-fg-secondary',
        square ? 'rounded-cn-sm' : 'rounded-cn-full',
        box,
      )}
    >
      {initials}
    </span>
  );
}

/**
 * DS-3 Poster (part of MediaCard, 02 §5.4). The neutral tile is the "poster
 * missing" state; real screens show the frame. Portrait uses an aspect token
 * that does not exist yet (`aspect-cn-portrait`).
 */
export function Poster({
  duration,
  portrait = false,
  dim = false,
  children,
  className,
}: {
  duration?: string;
  portrait?: boolean;
  dim?: boolean;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        'relative overflow-hidden rounded-cn-md bg-cn-surface-active',
        portrait ? 'aspect-[9/16]' : 'aspect-video',
        className,
      )}
    >
      <Film aria-hidden className={cx('absolute left-1/2 top-1/2 size-6 -translate-x-1/2 -translate-y-1/2 text-cn-fg-disabled', dim && 'opacity-50')} />
      {duration && (
        <span className="absolute bottom-1.5 right-1.5 rounded-cn-xs bg-cn-bg/80 px-1.5 font-cn-mono text-cn-caption tabular-nums text-cn-fg">
          {duration}
        </span>
      )}
      {children}
    </div>
  );
}

/**
 * DS-4 CreditMeter: one credit read-out replacing the three copies (audit 04
 * §6.4). Plan credits in accent, pack credits in neutral; the words carry the
 * meaning, the bar only shows proportion.
 */
export function CreditMeter({
  plan,
  planTotal,
  packs,
  compact = false,
}: {
  plan: number;
  planTotal: number;
  packs: number;
  compact?: boolean;
}) {
  const total = planTotal + packs;
  const planShare = Math.round((plan / total) * 100);
  const packShare = Math.round((packs / total) * 100);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-cn-label text-cn-fg-secondary">Credits</span>
        <span className="font-cn-mono text-cn-label tabular-nums text-cn-fg">{(plan + packs).toLocaleString('en-IN')}</span>
      </div>
      <div
        role="img"
        aria-label={`${plan.toLocaleString('en-IN')} plan credits and ${packs} pack credits left`}
        className="flex h-1.5 w-full gap-0.5 overflow-hidden rounded-cn-full bg-cn-surface-active"
      >
        <span className="h-full rounded-cn-full bg-cn-accent" style={{ width: `${planShare}%` }} />
        <span className="h-full rounded-cn-full bg-cn-fg-muted" style={{ width: `${packShare}%` }} />
      </div>
      {!compact && (
        <p className="text-cn-caption text-cn-fg-muted">
          {plan.toLocaleString('en-IN')} plan · {packs} pack · about 620 min of video
        </p>
      )}
    </div>
  );
}

/** DS-5 ActivityIndicator (02 §4.8): hidden when idle; a pill with a live dot and count. */
export function ActivityIndicator({
  jobs,
  defaultOpen = false,
  failed = false,
}: {
  jobs: ReadonlyArray<{ id: string; project: string; label: string; percent?: number }>;
  defaultOpen?: boolean;
  failed?: boolean;
}) {
  if (jobs.length === 0 && !failed) return null;
  const name = `${jobs.length} in progress${failed ? ', 1 needs attention' : ''}`;
  return (
    <Popover
      title="In progress"
      defaultOpen={defaultOpen}
      align="end"
      className="w-80"
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={name}
          className={cx(
            'inline-flex h-8 items-center gap-1.5 rounded-cn-full border border-cn-border-strong bg-cn-surface px-2.5 text-cn-label font-semibold text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg',
            focusRing,
          )}
        >
          <span aria-hidden className={cx('size-2 rounded-cn-full', failed ? 'bg-cn-danger' : 'bg-cn-accent motion-safe:animate-cn-pulse')} />
          <span aria-hidden className="font-cn-mono tabular-nums">
            {jobs.length}
          </span>
        </button>
      )}
    >
      <ul className="flex flex-col gap-3">
        {jobs.map((job) => (
          <li key={job.id} className="flex flex-col gap-1.5">
            <a href="#progress" className={cx('truncate rounded-cn-xs text-cn-label font-semibold text-cn-fg hover:underline', focusRing)}>
              {job.project}
            </a>
            <WorkingText className="text-cn-caption">{job.label}</WorkingText>
            {job.percent !== undefined && <ProgressBar label={`${job.project} progress`} value={job.percent} hideLabel size="sm" />}
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-cn-border pt-3 text-cn-caption text-cn-fg-muted">
        These keep going if you close the tab, except uploads from this tab. Finished work moves to notifications.
      </p>
    </Popover>
  );
}

/** DS-6 SourceChip: a `source` kind for ContextChip — the video a Home prompt works on. */
export function SourceChip({
  kind,
  title,
  meta,
  checking = false,
  onRemove,
}: {
  kind: 'youtube' | 'file';
  title: string;
  meta?: string;
  checking?: boolean;
  onRemove?: () => void;
}) {
  return (
    <span className="inline-flex h-8 max-w-full items-center gap-2 rounded-cn-sm border border-cn-border-strong bg-cn-surface pl-2 pr-0.5 text-cn-label text-cn-fg">
      <span aria-hidden className="inline-flex shrink-0 text-cn-fg-secondary [&_svg]:size-4">
        {kind === 'youtube' ? <Youtube /> : <FileVideo />}
      </span>
      <span className="sr-only">{kind === 'youtube' ? 'YouTube video' : 'Video file'}: </span>
      {checking ? <WorkingText className="truncate">Checking link</WorkingText> : <span className="truncate">{title}</span>}
      {meta && !checking && <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{meta}</span>}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${title} from the prompt`}
          className={cx(
            'inline-flex size-7 shrink-0 items-center justify-center rounded-cn-xs text-cn-fg-muted hover:bg-cn-surface-hover hover:text-cn-fg [&_svg]:size-3.5',
            focusRing,
          )}
        >
          <X aria-hidden />
        </button>
      )}
    </span>
  );
}

/** DS-7 SlashMenu (02 §4.3), static picture of the listbox above the prompt bar. */
export function SlashMenuList({
  rows,
  activeIndex = 0,
  label = 'Commands',
}: {
  rows: ReadonlyArray<{ id: string; command: string; description: string; group?: string; icon?: ReactNode }>;
  activeIndex?: number;
  label?: string;
}) {
  let lastGroup: string | undefined;
  return (
    <div role="listbox" aria-label={label} className="flex flex-col gap-0.5 rounded-cn-lg border border-cn-border-strong bg-cn-surface-raised p-1 shadow-cn-2">
      {rows.map((row, index) => {
        const heading = row.group && row.group !== lastGroup ? row.group : undefined;
        lastGroup = row.group;
        return (
          <div key={row.id} role="presentation">
            {heading && <p className="px-2 pb-1 pt-2 text-cn-caption text-cn-fg-muted">{heading}</p>}
            <div
              role="option"
              aria-selected={index === activeIndex}
              className={cx(
                'flex items-center gap-3 rounded-cn-sm px-2 py-1.5',
                index === activeIndex ? 'bg-cn-surface-hover' : '',
              )}
            >
              {row.icon && <span aria-hidden className="inline-flex text-cn-fg-muted [&_svg]:size-4">{row.icon}</span>}
              <span className="font-cn-mono text-cn-label text-cn-fg">{row.command}</span>
              <span className="min-w-0 flex-1 truncate text-cn-label text-cn-fg-secondary">{row.description}</span>
              {index === activeIndex && <ChevronRight aria-hidden className="size-3.5 text-cn-fg-muted" />}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** DS-8 FolderBadge: where a project lives, shown on cards and in breadcrumbs. */
export function FolderBadge({ name }: { name: string }) {
  return (
    <Badge icon={<Folder />} className="max-w-48">
      {name}
    </Badge>
  );
}
