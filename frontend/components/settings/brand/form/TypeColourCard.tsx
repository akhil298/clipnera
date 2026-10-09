'use client';

import { ColorSwatchPicker } from '@/components/ui';
import type { CreateBrandKitRequest } from '@/lib/api/brand/types';
import { cx } from '@/lib/design/styles';

import { RadioCards } from './_parts/RadioCards';
import { SettingsCard } from './_parts/SettingsCard';
import { BRAND_FONTS } from './options';
import type { UpdateKit } from './useBrandKitDraft';

const FONT_OPTIONS = BRAND_FONTS.map((font) => ({
  value: font.value,
  label: font.value,
  description: font.note,
  media: (
    <span aria-hidden className={cx('text-cn-title-lg font-bold leading-none text-cn-fg', font.className)}>
      Aa
    </span>
  ),
}));

/**
 * Font and the two brand colours. The colours are the user's own (content, not
 * chrome), so a custom hex is allowed here; the picker validates it.
 * `resetKey` remounts the pickers after Discard so their hex fields match the kit.
 */
export function TypeColourCard({ kit, update, resetKey }: { kit: CreateBrandKitRequest; update: UpdateKit; resetKey: number }) {
  return (
    <SettingsCard id="brand-type" title="Type and colour">
      <div className="space-y-6">
        <RadioCards
          legend="Font"
          options={FONT_OPTIONS}
          value={kit.preferred_font}
          onValueChange={(preferred_font) => update({ preferred_font })}
          className="grid-cols-1 sm:grid-cols-3"
        />
        <div key={resetKey} className="grid gap-6 sm:grid-cols-2">
          <ColorSwatchPicker
            label="Highlight colour"
            hint="The active word in captions."
            allowCustom
            value={kit.primary_color}
            onValueChange={(primary_color) => update({ primary_color })}
          />
          <ColorSwatchPicker
            label="Accent colour"
            hint="Supporting text and details."
            allowCustom
            value={kit.secondary_color}
            onValueChange={(secondary_color) => update({ secondary_color })}
          />
        </div>
      </div>
    </SettingsCard>
  );
}
