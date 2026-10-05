import { Badge } from '@/components/ui';
import { formatTimecode } from '@/lib/design/timecode';
import { LANDING_CLIPS } from '@/lib/landingMedia';
import { EXAMPLE_CLIPS, EXAMPLE_SOURCE } from '@/lib/marketing/content';

import { Section } from './Section';

const source = LANDING_CLIPS.podcast;
const percent = (seconds: number) => `${(seconds / EXAMPLE_SOURCE.seconds) * 100}%`;

/** "One podcast, three clips": the source on top, and each clip as a quote card that shows where it came from. */
export function ExampleOutput() {
  return (
    <Section
      id="example"
      title="One 58-minute podcast, three clips"
      intro="Clipnera reads the whole episode and hands back the moments that stand on their own, each opening on its hook."
      className="pt-0 lg:pt-0"
    >
      <div className="flex flex-col gap-4 rounded-cn-lg border border-cn-border bg-cn-surface p-4 sm:p-6">
        <div className="flex flex-wrap items-center gap-3">
          <img
            src={source.poster}
            alt={source.alt}
            loading="lazy"
            decoding="async"
            className="cn-media-edge aspect-video w-24 shrink-0 rounded-cn-md bg-cn-stage object-cover"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-cn-body font-semibold text-cn-fg">{EXAMPLE_SOURCE.title}</p>
            <p className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{formatTimecode(EXAMPLE_SOURCE.seconds)} · 3 moments found</p>
          </div>
          <Badge>Example output</Badge>
        </div>

        <div aria-hidden className="relative h-1 rounded-cn-full bg-cn-surface-active">
          {EXAMPLE_CLIPS.map((clip) => (
            <span key={clip.at} className="absolute -top-1 h-3 w-0.5 rounded-cn-full bg-cn-accent" style={{ left: percent(clip.at) }} />
          ))}
        </div>

        <ul className="grid gap-3 lg:grid-cols-3">
          {EXAMPLE_CLIPS.map((clip) => (
            <li key={clip.at} className="flex gap-3 rounded-cn-lg border border-cn-border bg-cn-bg p-3">
              <img
                src={source.poster}
                alt=""
                loading="lazy"
                decoding="async"
                className={`cn-media-edge aspect-cn-portrait w-16 shrink-0 rounded-cn-md bg-cn-stage object-cover ${clip.crop}`}
              />
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <blockquote className="text-cn-prose text-cn-fg">“{clip.quote}”</blockquote>
                <p className="mt-auto flex flex-wrap items-center gap-2 text-cn-caption text-cn-fg-muted">
                  <Badge>{clip.format}</Badge>
                  <span className="font-cn-mono tabular-nums">
                    <span className="sr-only">From </span>
                    {formatTimecode(clip.at)} · {formatTimecode(clip.length)}
                  </span>
                </p>
                <div aria-hidden className="relative h-1 rounded-cn-full bg-cn-surface-active">
                  <span className="absolute inset-y-0 bg-cn-accent/30" style={{ left: percent(clip.at), width: percent(clip.length) }} />
                  <span className="absolute -top-0.5 h-2 w-0.5 rounded-cn-full bg-cn-accent" style={{ left: percent(clip.at) }} />
                </div>
              </div>
            </li>
          ))}
        </ul>

        <p className="text-cn-caption text-cn-fg-muted">
          Sample clips for illustration. Yours come from your own footage, and you review every clip before anything is posted.
        </p>
      </div>
    </Section>
  );
}
