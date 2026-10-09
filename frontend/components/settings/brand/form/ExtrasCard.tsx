'use client';

import { Checkbox, Input } from '@/components/ui';
import { BRAND_KIT_LIMITS, type CreateBrandKitRequest } from '@/lib/api/brand/types';

import { SettingsCard } from './_parts/SettingsCard';
import type { UpdateKit } from './useBrandKitDraft';

/** Auto emojis and the end card's call to action. */
export function ExtrasCard({ kit, update }: { kit: CreateBrandKitRequest; update: UpdateKit }) {
  return (
    <SettingsCard id="brand-extras" title="Extras">
      <div className="space-y-6">
        <Checkbox
          label="Auto emojis in captions"
          description="Adds a matching emoji to words like “secret”, “money” or “rocket”."
          checked={kit.auto_emojis}
          onChange={(event) => update({ auto_emojis: event.target.checked })}
        />
        <Input
          label="End card call to action"
          value={kit.outro_cta_text}
          maxLength={BRAND_KIT_LIMITS.outroCta}
          placeholder="e.g. Follow @yourbrand for daily breakdowns"
          hint={`${kit.outro_cta_text.length} / ${BRAND_KIT_LIMITS.outroCta}`}
          onChange={(event) => update({ outro_cta_text: event.target.value })}
        />
      </div>
    </SettingsCard>
  );
}
