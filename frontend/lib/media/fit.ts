/**
 * Frame geometry for the preview: aspect sizes, fitting the stage into its box,
 * placing a clip's source inside the frame the way the renderer does, and the
 * platform safe zones. Pure, so `node --test` runs it directly.
 */
import type { Transform } from '../editor/timeline';

export type Aspect = '9:16' | '4:5' | '1:1' | '16:9';
export type SafeZonePlatform = 'shorts' | 'reels' | 'tiktok';

export interface Size {
  width: number;
  height: number;
}

export interface Rect extends Size {
  x: number;
  y: number;
}

/** Export size per aspect; mirrors output_dimensions() in backend/video_processor/geometry.py. */
export const ASPECT_SIZE: Record<Aspect, Size> = {
  '9:16': { width: 1080, height: 1920 },
  '4:5': { width: 1080, height: 1350 },
  '1:1': { width: 1080, height: 1080 },
  '16:9': { width: 1920, height: 1080 },
};

/** The named aspect closest to a frame size (a Timeline's width × height). */
export function aspectOf(size: Size): Aspect {
  const ratio = size.width / size.height;
  return (Object.keys(ASPECT_SIZE) as Aspect[]).reduce((best, aspect) => {
    const r = (a: Aspect) => ASPECT_SIZE[a].width / ASPECT_SIZE[a].height;
    return Math.abs(Math.log(r(aspect) / ratio)) < Math.abs(Math.log(r(best) / ratio)) ? aspect : best;
  }, '9:16' as Aspect);
}

/** The largest frame of `frame`'s shape inside `box`, centred (the stage in its zone). */
export function containRect(frame: Size, box: Size): Rect {
  const scale = Math.min(box.width / frame.width, box.height / frame.height);
  const width = frame.width * scale;
  const height = frame.height * scale;
  return { x: (box.width - width) / 2, y: (box.height - height) / 2, width, height };
}

/**
 * Where a source is drawn inside the frame, as shares of the frame (0..1 is the
 * frame; values outside are cropped). Timeline v1 semantics: the source fills
 * the frame, `scale` zooms in on top of that, and (x, y) is the source point kept
 * at the frame's centre, clamped so the source never leaves a gap.
 */
export function placeSource(source: Size, frame: Size, transform: Pick<Transform, 'x' | 'y' | 'scale'>): Rect {
  const cover = Math.max(frame.width / source.width, frame.height / source.height) * Math.max(transform.scale, 0.0001);
  const width = (source.width * cover) / frame.width;
  const height = (source.height * cover) / frame.height;
  const offset = (share: number, size: number) => {
    const ideal = 0.5 - share * size;
    return size >= 1 ? Math.min(0, Math.max(1 - size, ideal)) : ideal;
  };
  return { x: offset(transform.x, width), y: offset(transform.y, height), width, height };
}

/** A text item's centre at (x, y) as a share of the frame: its top-left anchor in px for a stage. */
export const pointOnStage = (stage: Size, at: Pick<Transform, 'x' | 'y'>) => ({ x: at.x * stage.width, y: at.y * stage.height });

export interface SafeZone {
  name: string;
  /** Margins the app's own UI covers, as shares of a 1080 × 1920 frame. */
  top: number;
  bottom: number;
  left: number;
  right: number;
  source: string;
}

/**
 * Where each app draws over a 9:16 video, measured on 1080 × 1920. These change
 * as the apps change; checked 5 Oct 2026.
 *
 * - Reels: Meta's Ads Guide for Instagram Reels, "leave roughly 14% of the top,
 *   35% of the bottom, and 6% on each side free of text, logos or key elements".
 * - Shorts: YouTube publishes no pixel template; these are the margins the common
 *   third-party templates agree on (180 px top, 390 px bottom, 60 px left,
 *   120 px right for the action column).
 * - TikTok: TikTok's in-feed ad templates as measured by third-party guides
 *   (130 px top, 484 px bottom, 140 px right; 60 px left assumed). Kept only as a
 *   safe-zone aid (screens/02-editor.md Q4).
 */
export const SAFE_ZONES: Record<SafeZonePlatform, SafeZone> = {
  reels: {
    name: 'Instagram Reels', top: 0.14, bottom: 0.35, left: 0.06, right: 0.06,
    source: 'https://www.facebook.com/business/ads-guide/video/instagram-reels',
  },
  shorts: {
    name: 'YouTube Shorts', top: 180 / 1920, bottom: 390 / 1920, left: 60 / 1080, right: 120 / 1080,
    source: 'Third-party Shorts templates (e.g. https://www.hopperhq.com/blog/youtube-shorts-dimensions/)',
  },
  tiktok: {
    name: 'TikTok', top: 130 / 1920, bottom: 484 / 1920, left: 60 / 1080, right: 140 / 1080,
    source: 'TikTok in-feed ad templates via third-party guides (e.g. https://adverthunt.com/tools/ad-safe-zone-checker/tiktok)',
  },
};

/** The area every listed platform leaves clear: the tightest margin on each side. */
export function combinedSafeZone(platforms: readonly SafeZonePlatform[] = ['shorts', 'reels']): Omit<SafeZone, 'name' | 'source'> {
  const zones = platforms.map((p) => SAFE_ZONES[p]);
  const most = (side: 'top' | 'bottom' | 'left' | 'right') => Math.max(0, ...zones.map((z) => z[side]));
  return { top: most('top'), bottom: most('bottom'), left: most('left'), right: most('right') };
}

/** The clear rectangle on a stage of `stage` px; safe zones only apply to 9:16 (null otherwise). */
export function safeRect(stage: Size, zone: Pick<SafeZone, 'top' | 'bottom' | 'left' | 'right'>): Rect | null {
  if (aspectOf(stage) !== '9:16') return null;
  return {
    x: zone.left * stage.width,
    y: zone.top * stage.height,
    width: (1 - zone.left - zone.right) * stage.width,
    height: (1 - zone.top - zone.bottom) * stage.height,
  };
}

/** The covered bands (rose-hatched in the preview), as stage rectangles. */
export function unsafeBands(stage: Size, zone: Pick<SafeZone, 'top' | 'bottom' | 'left' | 'right'>): Rect[] {
  const clear = safeRect(stage, zone);
  if (!clear) return [];
  return [
    { x: 0, y: 0, width: stage.width, height: clear.y },
    { x: 0, y: clear.y + clear.height, width: stage.width, height: stage.height - clear.y - clear.height },
    { x: 0, y: clear.y, width: clear.x, height: clear.height },
    { x: clear.x + clear.width, y: clear.y, width: stage.width - clear.x - clear.width, height: clear.height },
  ].filter((band) => band.width > 0 && band.height > 0);
}

/** Whether a vertical position (share of the frame, e.g. a caption's centre) clears the top and bottom bands. */
export const clearsVertically = (y: number, zone: Pick<SafeZone, 'top' | 'bottom'>): boolean =>
  y >= zone.top && y <= 1 - zone.bottom;
