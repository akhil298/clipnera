import { CaptionPreset } from '@/lib/types';

export interface CaptionPresetStyle {
  id: CaptionPreset;
  name: string;
  description: string;
  badge: string;
  font: string;
  previewTextColor: string;
  previewHighlight: string;
  bg: string;
}

export const CAPTION_PRESETS: CaptionPresetStyle[] = [
  {
    id: 'hormozi',
    name: 'Hormozi Viral',
    description: 'Bold uppercase, yellow/green highlights with dark backdrop',
    badge: 'Popular',
    font: 'Syne',
    previewTextColor: '#ffffff',
    previewHighlight: '#facc15',
    bg: '#000000',
  },
  {
    id: 'mrbeast',
    name: 'MrBeast Pop',
    description: 'High energy electric blue + bright red punch text',
    badge: 'High CTR',
    font: 'Plus Jakarta Sans',
    previewTextColor: '#ffffff',
    previewHighlight: '#38bdf8',
    bg: '#0f172a',
  },
  {
    id: 'karaoke_yellow',
    name: 'Karaoke Beat',
    description: 'Word-by-word active bouncing fill sync',
    badge: 'Top Watchtime',
    font: 'Syne',
    previewTextColor: '#94a3b8',
    previewHighlight: '#facc15',
    bg: '#18181b',
  },
  {
    id: 'cyberpunk',
    name: 'Cyber Neon',
    description: 'Neon cyan with purple ambient glow',
    badge: 'Tech / Gaming',
    font: 'JetBrains Mono',
    previewTextColor: '#e0f2fe',
    previewHighlight: '#38bdf8',
    bg: '#020617',
  },
  {
    id: 'minimal',
    name: 'Clean Minimal',
    description: 'Understated elegant typography for luxury & podcasts',
    badge: 'Aesthetic',
    font: 'Plus Jakarta Sans',
    previewTextColor: '#ffffff',
    previewHighlight: '#e2e8f0',
    bg: 'transparent',
  },
  {
    id: 'neon',
    name: 'Neon Glow',
    description: 'Vibrant pink and green neon effect',
    badge: 'Trending',
    font: 'Syne',
    previewTextColor: '#ffffff',
    previewHighlight: '#f0abfc',
    bg: '#000000',
  },
  {
    id: 'sunset',
    name: 'Sunset Warm',
    description: 'Warm orange and red gradient highlights',
    badge: 'Lifestyle',
    font: 'Syne',
    previewTextColor: '#ffffff',
    previewHighlight: '#fb923c',
    bg: '#1c1917',
  },
];
