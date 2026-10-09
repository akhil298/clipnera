'use client';

import { ImageIcon } from 'lucide-react';

import { Input, Slider } from '@/components/ui';
import { BRAND_KIT_LIMITS, type CreateBrandKitRequest } from '@/lib/api/brand/types';

import { PositionPicker } from './_parts/PositionPicker';
import { SettingsCard } from './_parts/SettingsCard';
import type { UpdateKit } from './useBrandKitDraft';

const { opacity, size } = BRAND_KIT_LIMITS;

/** Brand name, logo, and where and how strongly the watermark sits. */
export function IdentityCard({ kit, update, nameError }: { kit: CreateBrandKitRequest; update: UpdateKit; nameError?: string }) {
  return (
    <SettingsCard id="brand-identity" title="Identity and watermark">
      <div className="space-y-6">
        <Input
          id="brand-name"
          label="Brand or channel name"
          required
          value={kit.brand_name}
          maxLength={BRAND_KIT_LIMITS.brandName}
          placeholder="e.g. Priya Cooks"
          autoComplete="organization"
          error={nameError}
          onChange={(event) => update({ brand_name: event.target.value })}
        />

        <div className="space-y-1">
          <p className="text-cn-label font-semibold text-cn-fg">Logo</p>
          {/* NEEDS-BACKEND: POST /brand-kits/logo (L-API-11). No upload control until it exists. */}
          <p className="flex items-start gap-2 text-cn-body text-cn-fg-secondary">
            <ImageIcon aria-hidden className="mt-0.5 size-4 shrink-0 text-cn-fg-muted" />
            {kit.logo_url
              ? 'Your logo is used as the watermark. Replacing it from here is coming.'
              : 'Logo upload is coming. Your brand name is used as the watermark.'}
          </p>
        </div>

        <div className="flex flex-col gap-6 sm:flex-row">
          <PositionPicker value={kit.logo_position} onValueChange={(logo_position) => update({ logo_position })} />
          <div className="min-w-0 flex-1 space-y-6">
            <Slider
              label="Opacity"
              min={opacity.min}
              max={opacity.max}
              step={opacity.step}
              value={kit.logo_opacity}
              formatValue={(value) => `${value}%`}
              onValueChange={(logo_opacity) => update({ logo_opacity })}
            />
            <Slider
              label="Size"
              min={size.min}
              max={size.max}
              step={size.step}
              value={kit.logo_size}
              formatValue={(value) => `${value} px`}
              onValueChange={(logo_size) => update({ logo_size })}
            />
          </div>
        </div>
      </div>
    </SettingsCard>
  );
}
