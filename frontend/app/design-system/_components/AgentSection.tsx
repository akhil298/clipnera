'use client';

import { Captions, Scissors, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button, FollowUpChips, type Source, SourceCard, SourceList, StreamingText } from '@/components/ui';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

const REPLY = `### What I found
The strongest moment is at 12:40 [1], where Asha explains **why pricing is a product decision**. Two more are worth a look:

- The hiring story at 31:05 [2], tight and self-contained.
- A *quotable* line about fundraising at 48:12 [3].

I can cut all three to 9:16 with captions. Say \`go\` and I will start, or [read how scoring works](https://example.com/scoring).`;

const SOURCES: ReadonlyArray<Source> = [
  { id: 's1', kind: 'clip', title: 'Pricing is a product decision', origin: 'Episode 12 · 12:40–13:22', snippet: '"If you can\'t explain the price, you haven\'t finished the product."' },
  { id: 's2', kind: 'transcript', title: 'Our first ten hires', origin: 'Episode 12 · 31:05' },
  { id: 's3', kind: 'clip', title: 'Raising without a deck', origin: 'Episode 12 · 48:12' },
  { id: 's4', kind: 'broll', title: 'Whiteboard pricing sketch', origin: 'Clipnera library' },
  { id: 's5', kind: 'web', title: 'Pricing page teardown', origin: 'example.com', href: 'https://example.com' },
];

const CHUNK = 6;
const TICK_MS = 60;

export function AgentSection() {
  const [shown, setShown] = useState(REPLY.length);
  const [highlight, setHighlight] = useState<string>();
  const [seek, setSeek] = useState<number>();
  const [picked, setPicked] = useState<string>();
  const timer = useRef<ReturnType<typeof setInterval>>(undefined);
  const streaming = shown < REPLY.length;

  const replay = () => {
    clearInterval(timer.current);
    setShown(0);
    timer.current = setInterval(() => setShown((n) => Math.min(n + CHUNK, REPLY.length)), TICK_MS);
  };
  useEffect(() => {
    if (!streaming) clearInterval(timer.current);
  }, [streaming]);
  useEffect(() => () => clearInterval(timer.current), []);

  return (
    <GallerySection id="agent" title="Agent replies" intro="Perplexity-calm answers: streamed text, the sources behind it, and next steps.">
      <Specimen title="StreamingText" note={`Markdown-lite; word groups fade in 120 ms; sentence by sentence under reduced motion. Timecodes seek, [n] points at a source. ${seek !== undefined ? `Seek to ${seek} s.` : ''}`}>
        <div className="max-w-2xl space-y-4">
          <Button size="sm" variant="secondary" onClick={replay} loading={streaming} loadingLabel="Streaming">
            Replay stream
          </Button>
          <StreamingText
            text={REPLY.slice(0, shown)}
            streaming={streaming}
            onTimecode={setSeek}
            onCitation={(index) => setHighlight(SOURCES[index - 1]?.id)}
          />
        </div>
      </Specimen>

      <Specimen title="SourceList and SourceCard" note="One link or button covers each card. More than four collapse behind '+N more'. Pressing [1] above highlights card 1.">
        <div className="space-y-6">
          <SourceList sources={SOURCES} highlightedId={highlight} />
          <StateGrid className="lg:grid-cols-2">
            <State label="row variant" className="w-full">
              <SourceCard source={SOURCES[0]} index={1} variant="row" />
            </State>
            <State label="highlighted" className="w-full">
              <SourceCard source={SOURCES[3]} index={4} variant="row" highlighted />
            </State>
          </StateGrid>
        </div>
      </Specimen>

      <Specimen title="FollowUpChips" note={`A click fills the prompt bar; it never sends. ${picked ? `Filled: "${picked}".` : ''}`}>
        <StateGrid className="lg:grid-cols-3">
          <State label="chips" className="w-full">
            <FollowUpChips
              onPick={setPicked}
              items={[
                { id: 'cut', label: 'Cut all three', icon: <Scissors /> },
                { id: 'captions', label: 'Add bold captions', icon: <Captions /> },
                'Find two more',
              ]}
            />
          </State>
          <State label="list" className="w-full">
            <FollowUpChips variant="list" showLabel label="Related" onPick={setPicked} items={['Which clip will do best on Instagram?', 'Make the hook shorter', 'Add B-roll to the pricing clip']} />
          </State>
          <State label="loading" className="w-full">
            <FollowUpChips items={[]} onPick={setPicked} loading />
            <span className="inline-flex items-center gap-1 text-cn-caption text-cn-fg-muted">
              <Sparkles aria-hidden className="size-3" /> Thinking of next steps
            </span>
          </State>
        </StateGrid>
      </Specimen>
    </GallerySection>
  );
}
