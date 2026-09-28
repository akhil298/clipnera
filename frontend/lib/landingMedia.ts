import sources from './landingMedia.json';

/**
 * Footage shown on the landing page. Every clip is from Pexels (Pexels License:
 * free for commercial use, no attribution required). Posters load from the
 * Pexels image CDN; videos are served from /public/media/landing, downloaded by
 * `npm run media:landing`. Until a video file exists its poster stays on screen.
 */
export type LandingClipKey = keyof typeof sources;

export interface LandingClip {
  poster: string;
  video: string;
  alt: string;
}

export const LANDING_CLIPS = Object.fromEntries(
  Object.entries(sources).map(([key, { pexelsId, slug, alt }]) => [
    key,
    {
      poster: `https://images.pexels.com/videos/${pexelsId}/${slug}.jpeg?auto=compress&cs=tinysrgb&w=1280`,
      video: `/media/landing/${key}.mp4`,
      alt,
    },
  ]),
) as Record<LandingClipKey, LandingClip>;
