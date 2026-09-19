import { VideoProject } from '@/lib/types';

export const LANDING_SAMPLE_PROJECTS: VideoProject[] = [];

/**
 * Re-exported from the single derived list so the upload modal, the brand kit
 * and the editor all offer the same styles. This used to be a third hand-written
 * copy that had drifted from both the backend templates and captionPresets.ts.
 */
export { CAPTION_PRESETS } from '@/lib/data/captionPresets';
export type { CaptionPresetStyle } from '@/lib/data/captionPresets';
