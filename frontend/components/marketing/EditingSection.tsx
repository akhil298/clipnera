import { ArrowUp } from 'lucide-react';

import { ContextChip } from '@/components/ui';
import { LANDING_CLIPS } from '@/lib/landingMedia';

import { BurnedCaption } from './BurnedCaption';
import { EditorLink } from './EditorLink';
import { Section } from './Section';

const MOVES = [
  { title: 'Drop and describe', body: 'Upload footage, paste a YouTube link or reuse clips from earlier projects. Say what you want in your own words, Hinglish too.' },
  { title: 'Direct the edit', body: 'Clipnera builds the first cut on a real timeline. Point at a clip or a line and ask for a change, or drag, trim and split yourself.' },
  { title: 'Export or post', body: 'Download the MP4, or post to YouTube Shorts and Instagram Reels.' },
];

const FEATURES = [
  { title: 'Find any moment by meaning', body: 'Search “the part where she laughs about pricing” and jump straight to it, across every file.' },
  { title: 'A first cut that holds', body: 'The same engine behind your clips chooses the hook, the order and the pacing.' },
  { title: 'Chat or drag, one timeline', body: 'Your edits and Clipnera’s land on the same tracks, with one undo history.' },
  { title: 'Captions that stay clear', body: 'Word-by-word captions in five languages, kept clear of the app buttons.' },
  { title: 'B-roll and music, licensed', body: 'Cutaways and tracks from libraries licensed for commercial use, with AI-generated shots on Pro.' },
  { title: 'Bring your own Claude', body: 'Connect Claude Code or the Claude app and edit your projects from there, on your own plan.' },
];

const clip = LANDING_CLIPS.vlog;

/** `/editor` merged in (R1): three moves, a picture of an edit by prompt, and what the editor can do. */
export function EditingSection() {
  return (
    <div className="border-y border-cn-border bg-cn-surface">
      <Section
        id="editing"
        title="Then change anything with a sentence"
        intro="Select a clip or a few words and say what you want: shorter, a new hook, Hinglish captions, B-roll here. Each prompt becomes one version you can undo."
      >
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <ol className="flex flex-col gap-5">
            {MOVES.map((move, index) => (
              <li key={move.title} className="flex gap-4">
                <span
                  aria-hidden
                  className="inline-flex size-7 shrink-0 items-center justify-center rounded-cn-full border border-cn-border-strong font-cn-mono text-cn-caption text-cn-fg-secondary"
                >
                  {index + 1}
                </span>
                <span className="flex flex-col gap-1">
                  <span className="text-cn-body-lg font-semibold text-cn-fg">{move.title}</span>
                  <span className="text-cn-body text-cn-fg-secondary">{move.body}</span>
                </span>
              </li>
            ))}
            <li className="pl-11">
              <EditorLink />
            </li>
          </ol>

          <figure className="flex flex-col items-center gap-4">
            <div data-theme="dark" className="relative w-40 overflow-hidden rounded-cn-lg bg-cn-stage shadow-cn-2 aspect-cn-portrait">
              <img src={clip.poster} alt={clip.alt} loading="lazy" decoding="async" className="absolute inset-0 h-full w-full object-cover" />
              <BurnedCaption lines={['Yeh koi', 'nahi batata']} highlight="nahi" className="absolute inset-x-2 bottom-6 text-cn-label" />
            </div>
            <div aria-hidden className="flex w-full max-w-md flex-col gap-2 rounded-cn-xl border border-cn-border-strong bg-cn-surface-raised p-2 shadow-cn-2">
              <span>
                <ContextChip context={{ id: 'clip', kind: 'clip', label: 'The day I stopped chasing views', meta: '0:41' }} />
              </span>
              <span className="px-1.5 text-cn-body text-cn-fg">Make the hook punchier and add Hinglish captions</span>
              <span className="flex justify-end">
                <span className="inline-flex size-8 items-center justify-center rounded-cn-full bg-cn-surface-active text-cn-fg-secondary">
                  <ArrowUp className="size-4" />
                </span>
              </span>
            </div>
            <figcaption className="text-cn-caption text-cn-fg-muted">An edit asked for in a sentence, applied to one clip.</figcaption>
          </figure>
        </div>

        <ul className="mt-16 grid gap-px overflow-hidden rounded-cn-lg border border-cn-border bg-cn-border sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <li key={feature.title} className="flex flex-col gap-1.5 bg-cn-surface p-5">
              <h3 className="text-cn-body-lg font-semibold text-cn-fg">{feature.title}</h3>
              <p className="text-cn-body text-cn-fg-secondary">{feature.body}</p>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
