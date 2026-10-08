/**
 * Clip mode (02-editor.md §12): the editable document of one clip, and its mapping to and from
 * `ClipEditorSettings` (backend/clip_generation/schema.py), which `GET /clips/item/{id}` returns
 * as `editor_settings` and `PUT /clips/item/{id}/editor-settings` saves.
 *
 * Same fields and defaults as the legacy studio's `StudioDoc` (components/dashboard/
 * VideoEditorStudio.tsx `initialDoc` / `editorSettingsFor`), so nothing is lost. The mapping is
 * lossless for every saved field: highlights saved for words this transcript doesn't have are
 * carried in `orphanHighlights` and written back.
 *
 * Caption normalising is passed in (`normalizeCaptionConfig` from lib/utils/captionStyles), so this
 * file has no runtime imports and `node --test` runs it directly.
 */
import type { ClipEditorSettings } from '@/lib/api/clips';
import type {
  AspectRatio,
  AudioEnhancementConfig,
  AutoZoomConfig,
  BRollOverlay,
  CaptionConfig,
  HookTransitionConfig,
  SoundEffect,
  TranscriptSegment,
} from '@/lib/types';

export interface ClipDoc {
  aspectRatio: AspectRatio;
  captionConfig: CaptionConfig;
  hookTransition: HookTransitionConfig;
  watermarkEnabled: boolean;
  /** Burn captions into the export. */
  captionsEnabled: boolean;
  /** Overlay the clip title; only exported with captions on. */
  titleEnabled: boolean;
  /** Cut words by source start time; they stay in the transcript, struck through. */
  removedWords: number[];
  /** Words carry `highlighted`; saved as `transcript_edits.highlighted` by `sourceStart`. */
  transcriptSegments: TranscriptSegment[];
  /** Saved highlights with no word in this transcript, kept so a save never drops them. */
  orphanHighlights: number[];
  /** Preview only until saved anywhere (no field in ClipEditorSettings). */
  bRollOverlays: BRollOverlay[];
  /** Preview only (E-D6): "Sound effects play here but aren't saved or exported yet." */
  soundEffects: SoundEffect[];
  /** Preview only (E-D6). */
  autoZoom: AutoZoomConfig;
  /** Not saved until EB-23. */
  audioEnhancement: AudioEnhancementConfig;
}

export type NormaliseCaption = (saved: Partial<CaptionConfig> | undefined) => CaptionConfig;

const ASPECTS: ReadonlySet<string> = new Set<AspectRatio>(['9:16', '1:1', '4:5', '16:9']);

/** Same as the legacy studio's DEFAULT_AUDIO_ENHANCEMENT. */
export const DEFAULT_AUDIO_ENHANCEMENT: AudioEnhancementConfig = {
  aiDenoise: true,
  noiseSuppressionStrength: 90,
  deReverb: true,
  vocalClarityEq: true,
  humFilter: true,
};

/** Off: the render applies no zoom, so a preview zoom would show motion the export never has. */
export const DEFAULT_AUTO_ZOOM: AutoZoomConfig = { enabled: false, frequency: 'subtle', scale: 1.1 };

export interface ClipDocInput {
  settings: ClipEditorSettings | null | undefined;
  /** The clip's transcript as words with clip-relative times and `sourceStart` (legacy `buildTranscriptSegments`). */
  segments: TranscriptSegment[];
  normaliseCaption: NormaliseCaption;
}

export interface ClipDocLoad {
  doc: ClipDoc;
  /** False for a clip nobody has edited: the brand kit's caption look applies (`withBrandKitCaption`). */
  saved: boolean;
}

export function clipDocFromSettings({ settings, segments, normaliseCaption }: ClipDocInput): ClipDocLoad {
  const s = settings ?? {};
  const highlighted = new Set(s.transcript_edits?.highlighted ?? []);
  const hasHighlights = s.transcript_edits != null;
  const known = new Set<number>();
  const transcriptSegments = segments.map((segment) => ({
    ...segment,
    words: segment.words.map((word) => {
      if (word.sourceStart === undefined || !hasHighlights) return word;
      known.add(word.sourceStart);
      return { ...word, highlighted: highlighted.has(word.sourceStart) };
    }),
  }));
  return {
    saved: settings != null,
    doc: {
      aspectRatio: s.aspect_ratio && ASPECTS.has(s.aspect_ratio) ? (s.aspect_ratio as AspectRatio) : '9:16',
      captionConfig: normaliseCaption(s.caption_config ?? undefined),
      hookTransition: s.hook_transition ?? { mode: 'auto' },
      watermarkEnabled: s.watermark_enabled ?? true,
      captionsEnabled: s.captions_enabled ?? true,
      titleEnabled: s.title_enabled ?? true,
      removedWords: [...(s.transcript_edits?.removed ?? [])],
      transcriptSegments,
      orphanHighlights: [...highlighted].filter((at) => !known.has(at)),
      bRollOverlays: [],
      soundEffects: [],
      autoZoom: DEFAULT_AUTO_ZOOM,
      audioEnhancement: DEFAULT_AUDIO_ENHANCEMENT,
    },
  };
}

/** What `PUT /clips/item/{id}/editor-settings` saves: every field set, as the legacy studio sends it. */
export function settingsFromClipDoc(doc: ClipDoc): ClipEditorSettings {
  const highlighted = doc.transcriptSegments
    .flatMap((segment) => segment.words)
    .filter((word) => word.highlighted && word.sourceStart !== undefined)
    .map((word) => word.sourceStart as number);
  return {
    aspect_ratio: doc.aspectRatio,
    caption_config: doc.captionConfig,
    hook_transition: doc.hookTransition,
    watermark_enabled: doc.watermarkEnabled,
    captions_enabled: doc.captionsEnabled,
    title_enabled: doc.titleEnabled,
    transcript_edits: {
      removed: doc.removedWords,
      highlighted: [...highlighted, ...doc.orphanHighlights].sort((a, b) => a - b),
    },
  };
}

/**
 * A clip nobody has edited opens in the brand kit's caption look (legacy studio behaviour).
 * `presetConfig` is the kit's preset config (`getCaptionConfig(resolveCaptionPreset(kit.defaultPreset))`);
 * fonts stay the preset's, because the export can't render the kit's fonts.
 */
export function withBrandKitCaption(
  doc: ClipDoc,
  presetConfig: CaptionConfig,
  kit: { primaryColor: string; secondaryColor: string; autoEmojis: boolean },
): ClipDoc {
  return {
    ...doc,
    captionConfig: { ...presetConfig, highlightColor: kit.primaryColor, secondaryHighlightColor: kit.secondaryColor, emojisEnabled: kit.autoEmojis },
  };
}

/** Cut or restore words (by `sourceStart`); words without timing can't be cut. */
export function setWordsCut(doc: ClipDoc, sourceStarts: number[], cut: boolean): ClipDoc {
  const removed = new Set(doc.removedWords);
  for (const at of sourceStarts) (cut ? removed.add(at) : removed.delete(at));
  return { ...doc, removedWords: [...removed].sort((a, b) => a - b) };
}

/** Highlight or unhighlight words by id. */
export function setWordsHighlighted(doc: ClipDoc, wordIds: string[], highlighted: boolean): ClipDoc {
  const ids = new Set(wordIds);
  return {
    ...doc,
    transcriptSegments: doc.transcriptSegments.map((segment) =>
      segment.words.some((word) => ids.has(word.id))
        ? { ...segment, words: segment.words.map((word) => (ids.has(word.id) ? { ...word, highlighted } : word)) }
        : segment,
    ),
  };
}
