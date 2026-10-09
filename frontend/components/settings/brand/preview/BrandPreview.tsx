'use client';

import type { CreateBrandKitRequest, LogoPosition } from '@/lib/api/brand/types';
import { captionStyleFor } from '@/lib/api/brand/caption-presets';
import { cx } from '@/lib/design/styles';

import { brandCaptionConfig, CaptionStyleSample } from '../caption-sample';
import { fontClassFor } from '../form/options';

/** Frame widths: 256 beside the form, 240 above it on tablets, 160 in the phone disclosure. */
const SIZES = {
  lg: { frame: 'w-64', px: 256 },
  md: { frame: 'w-60', px: 240 },
  sm: { frame: 'w-40', px: 160 },
} as const;

/** Caption sizes are on a 1080-wide video. */
const VIDEO_WIDTH = 1080;
/** The watermark size is in px on a 360-wide phone screen (legacy preview scale). */
const PHONE_WIDTH = 360;

const CORNER: Record<LogoPosition, string> = {
  top_left: 'left-3 top-3',
  top_right: 'right-3 top-3',
  bottom_left: 'bottom-12 left-3',
  bottom_right: 'bottom-12 right-3',
};

export type BrandPreviewKit = Pick<
  CreateBrandKitRequest,
  | 'brand_name'
  | 'logo_url'
  | 'logo_position'
  | 'logo_opacity'
  | 'logo_size'
  | 'primary_color'
  | 'secondary_color'
  | 'preferred_font'
  | 'default_preset'
  | 'auto_emojis'
  | 'outro_cta_text'
>;

/**
 * The 9:16 phone frame: watermark in its corner at its opacity and size, a
 * caption sample in the default style with the kit's colours, and the end card
 * call to action. Always dark, because it stands in for footage (07 §1.3).
 */
export function BrandPreview({ kit, size = 'lg', className }: { kit: BrandPreviewKit; size?: keyof typeof SIZES; className?: string }) {
  const { frame, px } = SIZES[size];
  const scale = px / VIDEO_WIDTH;
  const style = captionStyleFor(kit.default_preset);
  const config = brandCaptionConfig(style.id, kit);
  const fontClass = fontClassFor(kit.preferred_font);
  const mark = Math.round((kit.logo_size * px) / PHONE_WIDTH);
  const name = kit.brand_name.trim() || 'Your brand';

  return (
    <figure className={cx('flex flex-col items-center gap-2', className)}>
      <div
        data-theme="dark"
        className={cx('relative aspect-cn-portrait overflow-hidden rounded-cn-xl border-4 border-cn-border-strong bg-cn-stage', frame)}
        role="img"
        aria-label={`Preview: ${name} watermark ${kit.logo_position.replace('_', ' ')}, ${style.name} captions${kit.outro_cta_text ? `, end card “${kit.outro_cta_text}”` : ''}`}
      >
        {/* A neutral stand-in speaker so the captions read over something footage-like. */}
        <div aria-hidden className="absolute inset-0 bg-cn-surface-sunken" />
        <div aria-hidden className="absolute left-1/2 top-1/4 aspect-square w-2/5 -translate-x-1/2 rounded-cn-full bg-cn-surface-hover" />
        <div aria-hidden className="absolute bottom-0 left-1/2 h-2/5 w-3/5 -translate-x-1/2 rounded-t-cn-3xl bg-cn-surface-hover" />

        <div aria-hidden className={cx('absolute flex items-center gap-1.5 rounded-cn-sm bg-cn-bg/60 px-1.5 py-1', CORNER[kit.logo_position])} style={{ opacity: kit.logo_opacity / 100 }}>
          {kit.logo_url ? (
            // The user's own logo from storage; next/image would need the bucket in next.config.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={kit.logo_url} alt="" className="object-contain" style={{ width: mark, height: mark }} />
          ) : (
            <span className={cx('font-bold leading-none text-cn-fg', fontClass)} style={{ fontSize: mark * 0.6 }}>
              {name}
            </span>
          )}
        </div>

        <CaptionStyleSample
          config={config}
          words={kit.auto_emojis ? ['THIS', 'CHANGES', 'EVERY', 'THING 🔥'] : undefined}
          fontSize={Math.max(9, Math.round(config.fontSize * scale))}
          className="absolute inset-x-2 -translate-y-1/2"
          style={{ top: `${config.positionY}%` }}
        />

        {kit.outro_cta_text.trim() && (
          <p aria-hidden className={cx('absolute inset-x-3 bottom-3 truncate rounded-cn-full bg-cn-bg/70 px-2 py-1 text-center text-cn-caption text-cn-fg', fontClass)}>
            {kit.outro_cta_text}
          </p>
        )}
      </div>
      <figcaption className="font-cn-mono text-cn-caption text-cn-fg-muted">9:16 · {style.name}</figcaption>
    </figure>
  );
}
