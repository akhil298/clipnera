'use client';

import { Scissors } from 'lucide-react';

import { Button } from '@/components/ui';
import { focusHeroPrompt } from '@/lib/marketing/heroFocus';

/** The bottom band: no second form, it sends you back to the one composer (R9). */
export function ClosingCta() {
  return (
    <section aria-labelledby="closing-title" className="border-t border-cn-border bg-cn-surface">
      <div className="mx-auto flex max-w-3xl flex-col items-center gap-5 px-4 py-24 text-center lg:py-32">
        <h2 id="closing-title" className="font-cn-sans text-cn-display-sm font-bold text-cn-fg sm:text-cn-display">
          Your next Shorts are already recorded.
        </h2>
        <Button size="lg" leadingIcon={<Scissors />} onClick={focusHeroPrompt}>
          Start with your video
        </Button>
        <p className="text-cn-label text-cn-fg-muted">Free plan, no card needed.</p>
      </div>
    </section>
  );
}
