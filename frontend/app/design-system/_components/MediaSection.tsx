import { Card, CardHeader } from '@/components/ui/Card';

import { GallerySection } from './Specimen';

const SPECIFIED = [
  { title: 'VideoPlayer chrome', body: 'Transport, scrubber as a slider, quality badge, captions toggle, full screen.' },
  { title: 'Timeline track and clip', body: 'Tracks, clip blocks, lock state, the 600 ms landing highlight, keyboard trimming.' },
  { title: 'AssetGrid', body: 'Virtualised grid with roving focus, multi-select, drag to timeline.' },
  { title: 'MediaCard', body: 'Poster, 150 ms hover preview preloaded on approach, duration, licence, actions.' },
  { title: 'SlashMenu, PromptQueue, ActivityIndicator, QualityBadge, VersionHistory item', body: 'Prompt-experience parts not yet built as code.' },
] as const;

/** The media set is specified in the doc only; this section points there. */
export function MediaSection() {
  return (
    <GallerySection
      id="media"
      title="Media and remaining prompt parts (spec only)"
      intro="Specified in docs/revamp/02-design-system.md §5–§6, to be built with the screens that use them."
    >
      <div className="grid gap-4 md:grid-cols-2">
        {SPECIFIED.map((item) => (
          <Card key={item.title}>
            <CardHeader title={item.title} description={item.body} />
          </Card>
        ))}
      </div>
    </GallerySection>
  );
}
