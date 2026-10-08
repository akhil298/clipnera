'use client';

import { AudioLines, Captions, Crop, Film, Library, Sparkles, Type } from 'lucide-react';
import type { ReactNode } from 'react';

import { Button } from '@/components/ui/Button';
import { MediaCard } from '@/components/ui/MediaCard';
import { ToolRailItem } from '@/components/ui/ToolRailItem';
import { Chip } from '@/components/ui/Chip';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Switch } from '@/components/ui/Switch';
import { cx, focusRing } from '@/lib/design/styles';

import { BROLL_ALTERNATES } from './sample';
import { TranscriptPanel } from './TranscriptPanel';

export type Tool = 'transcript' | 'captions' | 'hook' | 'library' | 'format' | 'audio';

export const TOOLS: ReadonlyArray<{ id: Tool; label: string; icon: ReactNode; shortcut: string }> = [
  { id: 'transcript', shortcut: '1', label: 'Transcript', icon: <Type /> },
  { id: 'captions', shortcut: '2', label: 'Captions', icon: <Captions /> },
  { id: 'hook', shortcut: '3', label: 'Hook', icon: <Sparkles /> },
  { id: 'library', shortcut: '4', label: 'Library', icon: <Library /> },
  { id: 'format', shortcut: '5', label: 'Format', icon: <Crop /> },
  { id: 'audio', shortcut: '6', label: 'Audio', icon: <AudioLines /> },
];

/** The left tool rail (was the studio's right-hand Inspector tabs; see Removals and moves). */
export function ToolRail({ tool, onTool, orientation = 'vertical' }: { tool: Tool | null; onTool: (tool: Tool | null) => void; orientation?: 'vertical' | 'horizontal' }) {
  return (
    <nav aria-label="Tools" className={cx('flex shrink-0 bg-cn-surface', orientation === 'vertical' ? 'w-14 flex-col items-center gap-1 py-2' : 'h-14 items-center justify-around border-t border-cn-border px-1')}>
      {TOOLS.map((item) => (
        <ToolRailItem
          key={item.id}
          label={item.label}
          icon={item.icon}
          shortcut={item.shortcut}
          layout={orientation === 'vertical' ? 'rail' : 'tab'}
          active={tool === item.id}
          onClick={() => onTool(tool === item.id ? null : item.id)}
        />
      ))}
    </nav>
  );
}

const STYLES = ['Bold pop', 'Karaoke', 'Clean line', 'Boxed', 'Neon edge', 'Typewriter'];

/** Tool panel content. Panels keep the studio's controls; only the frame changes. */
export function ToolPanel({
  tool,
  time,
  onSeek,
  onSelection,
  onOpenLibrary,
}: {
  tool: Tool;
  time: number;
  onSeek: (seconds: number) => void;
  onSelection: (text: string | null) => void;
  onOpenLibrary: () => void;
}) {
  if (tool === 'transcript') return <TranscriptPanel time={time} onSeek={onSeek} onSelection={onSelection} />;
  return (
    <section aria-label={TOOLS.find((item) => item.id === tool)?.label} className="flex min-h-0 flex-col gap-4 overflow-y-auto p-3">
      <h2 className="text-cn-label font-semibold">{TOOLS.find((item) => item.id === tool)?.label}</h2>
      {tool === 'captions' && (
        <>
          <ul aria-label="Caption styles" className="grid grid-cols-3 gap-2">
            {STYLES.map((style, index) => (
              <li key={style}>
                <button
                  type="button"
                  aria-pressed={index === 0}
                  className={cx(
                    'flex aspect-[4/3] w-full flex-col items-center justify-center gap-1 rounded-cn-md border text-cn-caption',
                    index === 0 ? 'border-cn-accent-border bg-cn-accent-subtle text-cn-accent-text' : 'border-cn-border bg-cn-surface-hover text-cn-fg-secondary',
                    focusRing,
                  )}
                >
                  <span className="font-extrabold">MOST NEVER</span>
                  {style}
                </button>
              </li>
            ))}
          </ul>
          <Button size="sm" variant="ghost">
            See all 21 styles
          </Button>
          <p className="text-cn-caption text-cn-fg-muted">Look, Motion, Position, Emojis and Background sections stay as in the clip studio. Hover a style to preview it on your clip.</p>
        </>
      )}
      {tool === 'hook' && (
        <>
          <label className="flex flex-col gap-1 text-cn-label">
            Title text
            <input defaultValue="Why ₹499 works" className={cx('h-9 rounded-cn-md border border-cn-control-border bg-cn-field px-2.5 text-cn-body', focusRing)} />
          </label>
          <SegmentedControl label="Transition into the clip" size="sm" defaultValue="auto" options={[{ value: 'auto', label: 'Auto' }, { value: 'presets', label: 'Presets' }, { value: 'mix', label: 'Mix' }, { value: 'off', label: 'Off' }]} />
          <p className="text-cn-caption text-cn-fg-muted">The title is now editable (it was read-only in the studio). Transition presets and Mix keep their controls.</p>
        </>
      )}
      {tool === 'library' && (
        <>
          <div className="flex gap-1.5">
            <Chip size="sm" selected>
              Clipnera library
            </Chip>
            <Chip size="sm">Your uploads</Chip>
          </div>
          <input aria-label="Search footage" placeholder="Search footage — try “drone shot of a city at night”" className={cx('h-9 rounded-cn-md border border-cn-control-border bg-cn-field px-2.5 text-cn-label', focusRing)} />
          <ul className="grid grid-cols-2 gap-2">
            {BROLL_ALTERNATES.map((shot) => (
              <li key={shot.id}>
                <MediaCard size="sm" title={shot.title} duration={shot.duration} meta={shot.source} actionLabel={`Add ${shot.title} at the playhead`} />
              </li>
            ))}
          </ul>
          <Button size="sm" variant="secondary" leadingIcon={<Film />} onClick={onOpenLibrary}>
            Open the full library
          </Button>
          <p className="text-cn-caption text-cn-fg-muted">Browse, filters and uploads belong to the library screens. Here: search, drag to the timeline, or + to add at the playhead.</p>
        </>
      )}
      {tool === 'format' && (
        <ul aria-label="Aspect ratio" className="grid grid-cols-2 gap-2">
          {[
            ['9:16', 'Vertical', '1080×1920'],
            ['1:1', 'Square', '1080×1080'],
            ['4:5', 'Portrait', '1080×1350'],
            ['16:9', 'Wide', '1920×1080'],
          ].map(([ratio, name, size], index) => (
            <li key={ratio}>
              <button
                type="button"
                aria-pressed={index === 0}
                className={cx('flex w-full flex-col items-start rounded-cn-md border p-2.5 text-left', index === 0 ? 'border-cn-accent-border bg-cn-accent-subtle' : 'border-cn-border', focusRing)}
              >
                <span className="font-cn-mono text-cn-label">{ratio}</span>
                <span className="text-cn-caption text-cn-fg-secondary">
                  {name} · {size}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {tool === 'audio' && (
        <>
          <Switch label="Reduce background noise" defaultChecked />
          <SegmentedControl label="Strength" size="sm" defaultValue="balanced" options={[{ value: 'light', label: 'Light' }, { value: 'balanced', label: 'Balanced' }, { value: 'tight', label: 'Tight' }]} />
          <Switch label="Level my voice" defaultChecked />
          <Button size="sm" variant="secondary">
            Hold to hear before
          </Button>
          <p className="text-cn-caption text-cn-fg-muted">Finished, not preview-only: these settings are saved with the clip and used in the export.</p>
        </>
      )}
    </section>
  );
}
