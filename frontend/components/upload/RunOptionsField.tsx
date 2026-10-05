'use client';

import { Lock } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Checkbox, Chip, Disclosure, InlineAlert, SegmentedControl, Switch, buttonClasses } from '@/components/ui';
import type { Entitlements } from '@/lib/api/credits';
import { OUTPUT_RATIOS, type OutputRatio } from '@/lib/api/pipeline';

import { LENGTH_OPTIONS, SCRIPT_OPTIONS, STRENGTH_OPTIONS, summarize, type RunOptions } from './options';

const FORMAT_LABEL: Record<OutputRatio, string> = {
  '9:16': '9:16 vertical',
  '4:5': '4:5 portrait',
  '1:1': '1:1 square',
  '16:9': '16:9 landscape',
};

const BILLING_HREF = '/dashboard/settings/billing';

interface RunOptionsFieldProps {
  value: RunOptions;
  onChange: (next: RunOptions) => void;
  plan: Entitlements | undefined;
  brollAllowed: boolean;
}

/** Formats, Studio voice, length and captions, closed by default behind a one-line summary (R34). */
export function RunOptionsField({ value, onChange, plan, brollAllowed }: RunOptionsFieldProps) {
  const [lockedNote, setLockedNote] = useState<OutputRatio | null>(null);
  const set = <K extends keyof RunOptions>(key: K, next: RunOptions[K]) => onChange({ ...value, [key]: next });
  const canChoose = !!plan?.features.custom_aspect_ratios;
  const unlocked = (ratio: OutputRatio) => ratio === '9:16' || (canChoose && !!plan?.aspect_ratios.includes(ratio));
  const extraShare = plan ? Math.round(plan.extra_aspect_ratio_credit_share * 100) : null;

  const toggleFormat = (ratio: OutputRatio) => {
    if (!unlocked(ratio)) return setLockedNote(ratio);
    setLockedNote(null);
    const has = value.formats.includes(ratio);
    // At least one format is always rendered; canonical order keeps the request and the summary stable.
    if (has && value.formats.length === 1) return;
    const next = has ? value.formats.filter((r) => r !== ratio) : [...value.formats, ratio];
    set('formats', OUTPUT_RATIOS.filter((r) => next.includes(r)));
  };

  return (
    <Disclosure title="Options" summary={summarize(value, brollAllowed)} variant="card" level={3}>
      <div className="flex flex-col gap-6">
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-cn-label font-semibold text-cn-fg">Formats</legend>
          <div className="flex flex-wrap gap-2">
            {OUTPUT_RATIOS.map((ratio) => {
              const open = unlocked(ratio);
              return (
                <Chip
                  key={ratio}
                  selected={value.formats.includes(ratio)}
                  aria-disabled={!open || undefined}
                  icon={open ? undefined : <Lock />}
                  onClick={() => toggleFormat(ratio)}
                >
                  {FORMAT_LABEL[ratio]}
                </Chip>
              );
            })}
          </div>
          <p className="text-cn-caption text-cn-fg-muted">
            {canChoose && extraShare !== null
              ? `The first format is included; each extra one adds ${extraShare}% of the cost.`
              : 'Every plan renders 9:16. More formats come with Pro.'}
          </p>
          {lockedNote && (
            <InlineAlert
              tone="info"
              live="status"
              onDismiss={() => setLockedNote(null)}
              action={
                <Link href={BILLING_HREF} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
                  See plans
                </Link>
              }
            >
              {`${FORMAT_LABEL[lockedNote]} isn’t on your plan. Pro renders every format.`}
            </InlineAlert>
          )}
        </fieldset>

        <div className="flex flex-col gap-3">
          <Switch
            label="Studio voice"
            description="Removes room echo, mic hiss, fan hum and background noise."
            checked={value.studioVoice}
            onCheckedChange={(checked) => set('studioVoice', checked)}
          />
          {value.studioVoice && (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <span aria-hidden className="text-cn-label text-cn-fg-secondary">
                  Strength
                </span>
                <SegmentedControl
                  label="Studio voice strength"
                  size="sm"
                  options={STRENGTH_OPTIONS}
                  value={value.strength}
                  onValueChange={(next) => set('strength', next)}
                />
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <Checkbox label="Remove echo" checked={value.removeEcho} onChange={(event) => set('removeEcho', event.target.checked)} />
                <Checkbox label="Voice clarity" checked={value.voiceClarity} onChange={(event) => set('voiceClarity', event.target.checked)} />
                <Checkbox label="50/60 Hz hum filter" checked={value.humFilter} onChange={(event) => set('humFilter', event.target.checked)} />
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <span aria-hidden className="text-cn-label font-semibold text-cn-fg">
            Clip length
          </span>
          <SegmentedControl
            label="Clip length"
            size="sm"
            options={LENGTH_OPTIONS}
            value={value.length}
            onValueChange={(next) => set('length', next)}
            className="self-start"
          />
        </div>

        <div className="flex flex-col gap-3">
          <Switch
            label="Story clips"
            description="Also stitches moments from across the video into one clip."
            checked={value.storyClips}
            onCheckedChange={(checked) => set('storyClips', checked)}
          />
          {brollAllowed && (
            <Switch
              label="B-roll cutaways"
              description="Adds matching footage where it fits. 5 credits per clip that gets B-roll."
              checked={value.broll}
              onCheckedChange={(checked) => set('broll', checked)}
            />
          )}
        </div>

        <div className="flex flex-col gap-2">
          <span aria-hidden className="text-cn-label font-semibold text-cn-fg">
            Hindi and Telugu captions
          </span>
          <SegmentedControl
            label="Hindi and Telugu caption script"
            size="sm"
            options={SCRIPT_OPTIONS}
            value={value.captionScript}
            onValueChange={(next) => set('captionScript', next)}
            className="self-start"
          />
          <p className="text-cn-caption text-cn-fg-muted">Auto writes Hinglish and Tenglish in Roman letters.</p>
        </div>
      </div>
    </Disclosure>
  );
}
