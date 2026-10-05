'use client';

import { Download, Heart, Plus, Search, Settings, Sparkles, Trash2, Volume2 } from 'lucide-react';
import { useState } from 'react';

import { Badge, type BadgeTone, type Status, StatusBadge } from '@/components/ui/Badge';
import { Button, type ButtonVariant } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Chip } from '@/components/ui/Chip';
import { IconButton, type IconButtonVariant } from '@/components/ui/IconButton';
import { Input } from '@/components/ui/Input';
import { Kbd } from '@/components/ui/Kbd';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Switch } from '@/components/ui/Switch';
import { Textarea } from '@/components/ui/Textarea';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

const BUTTON_VARIANTS: ReadonlyArray<ButtonVariant> = ['primary', 'secondary', 'ghost', 'danger'];
const ICON_VARIANTS: ReadonlyArray<IconButtonVariant> = ['ghost', 'secondary', 'primary', 'danger'];
const BADGE_TONES: ReadonlyArray<BadgeTone> = ['neutral', 'accent', 'success', 'danger', 'info'];
const STATUSES: ReadonlyArray<Status> = ['processing', 'ready', 'failed', 'scheduled', 'paused', 'draft'];
const FILTERS = ['Podcast', 'Interview', 'Keynote', 'Webinar'] as const;

export function ControlsSection() {
  const [filters, setFilters] = useState<ReadonlyArray<string>>(['Podcast']);
  const [muted, setMuted] = useState(false);
  const [notify, setNotify] = useState(true);
  const [view, setView] = useState<'grid' | 'list'>('grid');

  const toggleFilter = (filter: string) =>
    setFilters((current) => (current.includes(filter) ? current.filter((item) => item !== filter) : [...current, filter]));

  return (
    <GallerySection
      id="controls"
      title="Controls"
      intro="Hover and keyboard focus are live: move the pointer over a control or press Tab. Every other state is shown side by side."
    >
      <Specimen title="Button" note="One primary per view. Loading keeps the label (or a present-tense one), keeps focus and sweeps a bar; no spinner.">
        <div className="space-y-6">
          {BUTTON_VARIANTS.map((variant) => (
            <StateGrid key={variant}>
              <State label={`${variant}`}>
                <Button variant={variant}>{variant === 'danger' ? 'Delete project' : 'Create clips'}</Button>
              </State>
              <State label="with icon">
                <Button variant={variant} leadingIcon={variant === 'danger' ? <Trash2 /> : <Sparkles />}>
                  {variant === 'danger' ? 'Delete' : 'Find moments'}
                </Button>
              </State>
              <State label="disabled">
                <Button variant={variant} disabled>
                  Create clips
                </Button>
              </State>
              <State label="loading">
                <Button variant={variant} loading loadingLabel="Saving">
                  Save
                </Button>
              </State>
            </StateGrid>
          ))}
          <StateGrid>
            <State label="size sm">
              <Button size="sm">Export</Button>
            </State>
            <State label="size md">
              <Button size="md">Export</Button>
            </State>
            <State label="size lg (touch)">
              <Button size="lg" trailingIcon={<Download />}>
                Export
              </Button>
            </State>
            <State label="full width" className="col-span-2 sm:col-span-1">
              <Button fullWidth variant="secondary">
                Continue
              </Button>
            </State>
          </StateGrid>
        </div>
      </Specimen>

      <Specimen title="IconButton" note="Always has a label: it is the accessible name and the tooltip.">
        <div className="space-y-6">
          <StateGrid>
            {ICON_VARIANTS.map((variant) => (
              <State key={variant} label={variant}>
                <IconButton variant={variant} label={variant === 'danger' ? 'Delete clip' : 'Add clip'} icon={variant === 'danger' ? <Trash2 /> : <Plus />} />
              </State>
            ))}
          </StateGrid>
          <StateGrid>
            <State label="toggle (pressed)">
              <IconButton label={muted ? 'Unmute' : 'Mute'} icon={<Volume2 />} pressed={muted} onClick={() => setMuted(!muted)} />
            </State>
            <State label="disabled">
              <IconButton label="Settings" icon={<Settings />} disabled />
            </State>
            <State label="loading">
              <IconButton label="Downloading" icon={<Download />} variant="secondary" loading />
            </State>
            <State label="sizes sm / md / lg">
              <div className="flex items-center gap-2">
                <IconButton label="Like (small)" icon={<Heart />} size="sm" />
                <IconButton label="Like (medium)" icon={<Heart />} size="md" />
                <IconButton label="Like (large)" icon={<Heart />} size="lg" />
              </div>
            </State>
          </StateGrid>
        </div>
      </Specimen>

      <Specimen title="Input and Textarea" note="Label above, help below, error replaces nothing: it is added above the help text and read with the field.">
        <div className="grid gap-6 md:grid-cols-2">
          <Input label="Project name" placeholder="Founder podcast, episode 12" hint="Shown on your project card." />
          <Input label="Video link" defaultValue="youtube.com/watch?v=" error="That link is not a full YouTube address. Paste the whole link." required />
          <Input label="Search clips" leading={<Search />} placeholder="Search by words said in the clip" size="lg" />
          <Input label="Workspace" defaultValue="Personal" disabled hint="Only the owner can rename it." />
          <Textarea label="Hook text" placeholder="The first line viewers read" maxLength={120} minRows={2} />
          <Textarea label="Notes" defaultValue="Too long" error="Keep it under 20 words." minRows={2} />
        </div>
      </Specimen>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="Checkbox">
          <div className="space-y-4">
            <Checkbox label="Burn captions into the video" />
            <Checkbox label="Remove filler words" description="Cuts um, uh and like." defaultChecked />
            <Checkbox label="Select all clips" indeterminate description="3 of 8 selected" />
            <Checkbox label="Add music" disabled />
            <Checkbox label="I am 18 or older" error="Tick this to continue." required />
          </div>
        </Specimen>
        <Specimen title="Switch" note="For settings that apply at once. Inside a form that is submitted, use Checkbox.">
          <div className="space-y-4">
            <Switch label="Email me when a long job finishes" description="Jobs over 5 minutes." checked={notify} onCheckedChange={setNotify} />
            <Switch label="Auto-reframe" defaultChecked />
            <Switch label="Preview-quality playback" disabled />
            <Switch label="Loop" labelPosition="end" />
          </div>
        </Specimen>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="SegmentedControl" note="Radio group: Tab enters at the selection, arrows move and choose.">
          <div className="flex flex-col items-start gap-4">
            <SegmentedControl
              label="View"
              options={[
                { value: 'grid', label: 'Grid' },
                { value: 'list', label: 'List' },
              ]}
              value={view}
              onValueChange={setView}
            />
            <SegmentedControl
              label="Aspect ratio"
              size="sm"
              options={[
                { value: '9:16', label: '9:16' },
                { value: '1:1', label: '1:1' },
                { value: '16:9', label: '16:9' },
                { value: '4:5', label: '4:5', disabled: true },
              ]}
            />
          </div>
        </Specimen>
        <Specimen title="Chip" note="Toggle chips filter; action chips (suggestions) fill the prompt bar and never send.">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by type">
              {FILTERS.map((filter) => (
                <Chip key={filter} selected={filters.includes(filter)} onClick={() => toggleFilter(filter)}>
                  {filter}
                </Chip>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Chip icon={<Sparkles />}>Find the 5 best moments</Chip>
              <Chip size="sm">Add captions</Chip>
              <Chip disabled>Disabled</Chip>
            </div>
          </div>
        </Specimen>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="Badge and StatusBadge" note="Text always carries the meaning; colour repeats it.">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {BADGE_TONES.map((tone) => (
                <Badge key={tone} tone={tone}>
                  {tone}
                </Badge>
              ))}
              <Badge tone="accent" icon={<Sparkles />}>
                Pro
              </Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              {STATUSES.map((status) => (
                <StatusBadge key={status} status={status} />
              ))}
            </div>
          </div>
        </Specimen>
        <Specimen title="Kbd">
          <ul className="space-y-2 text-cn-label text-cn-fg-secondary">
            <li className="flex items-center justify-between">
              Focus the prompt <Kbd keys={['⌘', 'K']} />
            </li>
            <li className="flex items-center justify-between">
              Undo the last edit <Kbd keys={['⌘', 'Z']} />
            </li>
            <li className="flex items-center justify-between">
              New line in the prompt <Kbd keys={['⇧', '↵']} />
            </li>
            <li className="flex items-center justify-between">
              Play / pause <Kbd keys={['Space']} />
            </li>
          </ul>
        </Specimen>
      </div>
    </GallerySection>
  );
}
