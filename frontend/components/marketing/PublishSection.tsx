import { Download, Instagram, Youtube } from 'lucide-react';

import { Section } from './Section';

const DESTINATIONS = [
  { icon: <Youtube />, title: 'YouTube Shorts', body: 'Post now, or schedule on Pro. Title and hashtags suggested, yours to edit.' },
  { icon: <Instagram />, title: 'Instagram Reels', body: 'Post now, or schedule on Pro, with a caption you approve.' },
  { icon: <Download />, title: 'Anywhere else', body: 'Download the MP4 and post it wherever your audience is.' },
];

/** Only YouTube and Instagram are claimed for direct posting (D3). */
export function PublishSection() {
  return (
    <Section id="publish" title="Straight to where people scroll" intro="You review every clip before it goes out. Nothing is posted on its own.">
      <ul className="grid gap-4 sm:grid-cols-3">
        {DESTINATIONS.map((destination) => (
          <li key={destination.title} className="flex gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-5">
            <span aria-hidden className="inline-flex text-cn-fg-secondary [&_svg]:size-6">
              {destination.icon}
            </span>
            <span className="flex flex-col gap-1">
              <span className="text-cn-body-lg font-semibold text-cn-fg">{destination.title}</span>
              <span className="text-cn-body text-cn-fg-secondary">{destination.body}</span>
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}
