'use client';

import Link from 'next/link';

import { Switch } from '@/components/ui';
import type { ExportLookOptions } from '@/lib/api/export/types';
import { cx, focusRing } from '@/lib/design/styles';

/** What the plan and the channel intro allow. */
export interface LookLocks {
  watermarkForced: boolean;
  introOnPlan: boolean;
  introReady: boolean;
}

export interface ExportLookFieldsProps {
  value: ExportLookOptions;
  onChange: (value: ExportLookOptions) => void;
  locks: LookLocks;
  /** The caption style's name, e.g. "Bold Pop". */
  styleName?: string;
}

const INTRO_HREF = '/dashboard/brand-kit#channel-intro';

/** "In the video" (editor §11.1), moved from the legacy Export ▾ menu. */
export function ExportLookFields({ value, onChange, locks, styleName }: ExportLookFieldsProps) {
  const set = (changes: Partial<ExportLookOptions>) => onChange({ ...value, ...changes });
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="mb-2 text-cn-label font-semibold text-cn-fg">In the video</legend>
      <Switch
        label="Captions burned in"
        description={styleName ? `${styleName} style` : undefined}
        checked={value.burn_subtitles}
        onCheckedChange={(burn_subtitles) => set({ burn_subtitles })}
      />
      <Switch
        label="Title text"
        description={value.burn_subtitles ? 'The headline at the top of the video' : 'Needs captions burned in'}
        checked={value.burn_subtitles && value.show_title}
        disabled={!value.burn_subtitles}
        onCheckedChange={(show_title) => set({ show_title })}
      />
      <Switch
        label="Clipnera watermark"
        description={locks.watermarkForced ? 'Paid plans can turn it off' : undefined}
        checked={locks.watermarkForced || value.watermark_enabled}
        disabled={locks.watermarkForced}
        onCheckedChange={(watermark_enabled) => set({ watermark_enabled })}
      />
      <Switch
        label="Channel intro"
        description={
          !locks.introOnPlan ? (
            'On the Pro plan'
          ) : locks.introReady ? (
            'Plays before the clip'
          ) : (
            <>
              Create it in{' '}
              <Link href={INTRO_HREF} className={cx('rounded-cn-sm text-cn-accent-text underline underline-offset-2 hover:text-cn-fg', focusRing)}>
                Brand kit
              </Link>{' '}
              first
            </>
          )
        }
        checked={locks.introOnPlan && locks.introReady && value.channel_intro}
        disabled={!locks.introOnPlan || !locks.introReady}
        onCheckedChange={(channel_intro) => set({ channel_intro })}
      />
    </fieldset>
  );
}
