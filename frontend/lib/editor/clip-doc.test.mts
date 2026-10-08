import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import './dev/resolve-hooks.mts';

const { clipDocFromSettings, settingsFromClipDoc, setWordsCut, setWordsHighlighted, withBrandKitCaption } = await import('./clip-doc.ts');

type Input = Parameters<typeof clipDocFromSettings>[0];
type Caption = ReturnType<Input['normaliseCaption']>;

/** Stand-in for normalizeCaptionConfig: preset defaults under whatever was saved. */
const DEFAULT_CAPTION = { preset: 'karaoke', fontSize: 64, positionY: 72, highlightColor: '#fff', secondaryHighlightColor: '#000', emojisEnabled: false } as unknown as Caption;
const normaliseCaption = (saved?: Partial<Caption>) => ({ ...DEFAULT_CAPTION, ...saved }) as Caption;

const word = (id: string, sourceStart?: number, highlighted?: boolean) => ({ id, text: id, start: 0, end: 1, sourceStart, highlighted });
const segments = () => [
  { id: 's1', speaker: 'A', speakerColor: '', start: 0, end: 3, text: 'a b c', words: [word('a', 10.5), word('b', 11, true), word('c')] },
  { id: 's2', speaker: 'A', speakerColor: '', start: 3, end: 5, text: 'd', words: [word('d', 12.25)] },
];

const full = {
  aspect_ratio: '1:1',
  caption_config: { ...DEFAULT_CAPTION, fontSize: 80 },
  hook_transition: { mode: 'preset' as const, preset_id: 'whip' },
  watermark_enabled: false,
  captions_enabled: true,
  title_enabled: false,
  transcript_edits: { removed: [11], highlighted: [10.5, 12.25, 99] },
};

describe('clip doc ↔ ClipEditorSettings', () => {
  it('round-trips every saved field, including highlights with no word here', () => {
    const { doc, saved } = clipDocFromSettings({ settings: full, segments: segments(), normaliseCaption });
    assert.equal(saved, true);
    assert.deepEqual(doc.orphanHighlights, [99]);
    assert.equal(doc.transcriptSegments[0].words[1].highlighted, false, 'saved highlights replace the automatic picks');
    assert.deepEqual(settingsFromClipDoc(doc), full);
  });

  it('opens an unedited clip with the studio defaults', () => {
    const { doc, saved } = clipDocFromSettings({ settings: null, segments: segments(), normaliseCaption });
    assert.equal(saved, false);
    assert.deepEqual(
      [doc.aspectRatio, doc.hookTransition, doc.watermarkEnabled, doc.captionsEnabled, doc.titleEnabled, doc.removedWords, doc.autoZoom.enabled],
      [['9:16'][0], { mode: 'auto' }, true, true, true, [], false],
    );
    assert.equal(doc.transcriptSegments[0].words[1].highlighted, true, 'automatic picks stay without saved edits');
    assert.deepEqual(settingsFromClipDoc(doc).transcript_edits, { removed: [], highlighted: [11] });
  });

  it('falls back to 9:16 for an aspect the editor does not know', () => {
    assert.equal(clipDocFromSettings({ settings: { aspect_ratio: '3:2' }, segments: [], normaliseCaption }).doc.aspectRatio, '9:16');
  });

  it('cuts, restores and highlights words', () => {
    let { doc } = clipDocFromSettings({ settings: full, segments: segments(), normaliseCaption });
    doc = setWordsCut(doc, [12.25, 10.5], true);
    doc = setWordsCut(doc, [11], false);
    doc = setWordsHighlighted(doc, ['b'], true);
    const out = settingsFromClipDoc(doc).transcript_edits!;
    assert.deepEqual(out.removed, [10.5, 12.25]);
    assert.deepEqual(out.highlighted, [10.5, 11, 12.25, 99]);
  });

  it('applies the brand kit look on top of the preset', () => {
    const { doc } = clipDocFromSettings({ settings: null, segments: [], normaliseCaption });
    const branded = withBrandKitCaption(doc, normaliseCaption({ fontSize: 70 }), { primaryColor: '#f5a623', secondaryColor: '#222', autoEmojis: true });
    assert.deepEqual(
      [branded.captionConfig.fontSize, branded.captionConfig.highlightColor, branded.captionConfig.secondaryHighlightColor, branded.captionConfig.emojisEnabled],
      [70, '#f5a623', '#222', true],
    );
  });
});
