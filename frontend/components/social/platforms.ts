import type { SocialPlatform } from '@/lib/api';

/** Display details per platform. Behaviour and limits come from the API. */
export const PLATFORM_STYLE: Record<SocialPlatform, { name: string; color: string }> = {
  youtube: { name: 'YouTube Shorts', color: 'from-red-600 to-rose-700' },
  tiktok: { name: 'TikTok', color: 'from-pink-500 to-rose-600' },
  instagram: { name: 'Instagram Reels', color: 'from-purple-500 to-pink-500' },
  x: { name: 'X (Twitter)', color: 'from-neutral-700 to-neutral-900' },
};

export const PLATFORM_ORDER: SocialPlatform[] = ['youtube', 'tiktok', 'instagram', 'x'];

/** 142800 -> "142.8K". */
export function formatAudience(count: number | null): string {
  if (count === null) return 'Hidden';
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(count);
}

/** Where the OAuth callback page sends the user back to. */
export const SOCIAL_SETTINGS_PATH = '/dashboard/settings?tab=social';
