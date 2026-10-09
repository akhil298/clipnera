'use client';

import { Lock } from 'lucide-react';
import { useMemo } from 'react';

import { Badge } from '@/components/ui';
import { CAPTION_CATALOGUE, isStyleOnPlan } from '@/lib/api/brand/caption-presets';
import type { CreateBrandKitRequest } from '@/lib/api/brand/types';
import type { Entitlements } from '@/lib/api/credits';

import { brandCaptionConfig, CaptionStyleSample } from '../caption-sample';
import { RadioCards } from './_parts/RadioCards';
import { SettingsCard } from './_parts/SettingsCard';
import type { UpdateKit } from './useBrandKitDraft';

/** Card samples are 14 px tall-ish: the template's 1080-wide size scaled into the card. */
const sampleSize = (fontSize: number) => Math.round(Math.min(20, Math.max(11, fontSize * 0.21)));

/**
 * The default caption style: the real catalogue (21 styles), each with a live
 * sample in the kit's colours. Styles outside the plan carry a Pro badge; they
 * can still be picked to preview, and Save explains the plan.
 */
export function CaptionStyleCard({
  kit,
  update,
  entitlements,
}: {
  kit: CreateBrandKitRequest;
  update: UpdateKit;
  entitlements: Entitlements | undefined;
}) {
  const { primary_color, secondary_color, auto_emojis } = kit;
  const options = useMemo(
    () =>
      CAPTION_CATALOGUE.map((style) => {
        const config = brandCaptionConfig(style.id, { primary_color, secondary_color, auto_emojis });
        return {
          value: style.id as string,
          label: style.name,
          description: style.badge,
          badge: isStyleOnPlan(style.id, entitlements) ? undefined : (
            <Badge tone="neutral" icon={<Lock />}>
              Pro
            </Badge>
          ),
          media: (
            <div data-theme="dark" className="flex h-14 items-center justify-center overflow-hidden rounded-cn-md bg-cn-stage px-2">
              <CaptionStyleSample config={config} fontSize={sampleSize(config.fontSize)} />
            </div>
          ),
        };
      }),
    [primary_color, secondary_color, auto_emojis, entitlements],
  );

  return (
    <SettingsCard
      id="brand-caption-style"
      title="Default caption style"
      description="New clips start with this style and your colours. You can change it on any clip."
      actions={<span className="font-cn-mono text-cn-caption text-cn-fg-muted">{CAPTION_CATALOGUE.length} styles</span>}
    >
      <div className="caption-preset-scroll -m-1 max-h-96 overflow-y-auto p-1">
        <RadioCards
          legend="Default caption style"
          hideLegend
          options={options}
          value={kit.default_preset}
          onValueChange={(default_preset) => update({ default_preset })}
          className="grid-cols-2 lg:grid-cols-3"
          cardClassName="p-2"
        />
      </div>
    </SettingsCard>
  );
}
