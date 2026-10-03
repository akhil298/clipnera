'use client';

import { Ellipsis, FolderOpen, Search, Upload } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardFooter, CardHeader, cardLinkOverlay } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { type ProgressStep, ProgressSteps } from '@/components/ui/ProgressSteps';
import { Skeleton, SkeletonGroup, SkeletonText } from '@/components/ui/Skeleton';
import { Tab, TabList, TabPanel, Tabs } from '@/components/ui/Tabs';
import { cx, focusRing } from '@/lib/design/styles';

import { GallerySection, Specimen, State } from './Specimen';

const UPLOAD_STEPS: ReadonlyArray<ProgressStep> = [
  { id: 'upload', label: 'Upload', description: '1.2 GB', status: 'done' },
  { id: 'transcribe', label: 'Transcribe', description: '42 of 61 minutes', status: 'active' },
  { id: 'moments', label: 'Find moments', status: 'upcoming' },
  { id: 'ready', label: 'Clips ready', status: 'upcoming' },
];

const FAILED_STEPS: ReadonlyArray<ProgressStep> = [
  { id: 'upload', label: 'Upload', status: 'done' },
  { id: 'transcribe', label: 'Transcribe', description: 'The audio track could not be read.', status: 'failed' },
  { id: 'moments', label: 'Find moments', status: 'upcoming' },
];

export function DisplaySection() {
  const [selected, setSelected] = useState(false);

  return (
    <GallerySection id="display" title="Display" intro="Structure and feedback: tabs, cards, empty and loading states, progress.">
      <Specimen title="Tabs" note="Automatic activation: arrows move and select. Underline for page sections, pill for panel switches.">
        <div className="space-y-8">
          <Tabs defaultValue="profile">
            <TabList label="Settings sections">
              <Tab value="profile">Profile</Tab>
              <Tab value="billing">Plan and billing</Tab>
              <Tab value="social">Social accounts</Tab>
              <Tab value="team" disabled>
                Team
              </Tab>
            </TabList>
            <TabPanel value="profile" className="pt-4 text-cn-body text-cn-fg-secondary">
              Profile settings.
            </TabPanel>
            <TabPanel value="billing" className="pt-4 text-cn-body text-cn-fg-secondary">
              Plan and billing.
            </TabPanel>
            <TabPanel value="social" className="pt-4 text-cn-body text-cn-fg-secondary">
              YouTube and Instagram.
            </TabPanel>
          </Tabs>
          <Tabs defaultValue="steps" variant="pill">
            <TabList label="Run details" className="w-fit">
              <Tab value="steps">Steps</Tab>
              <Tab value="changes">Changes</Tab>
            </TabList>
            <TabPanel value="steps" className="pt-3 text-cn-body text-cn-fg-secondary">
              What the assistant did.
            </TabPanel>
            <TabPanel value="changes" className="pt-3 text-cn-body text-cn-fg-secondary">
              The timeline operations, in plain words.
            </TabPanel>
          </Tabs>
        </div>
      </Specimen>

      <Specimen title="Card" note="The card is never the click target itself: one real link inside covers it, other buttons sit above.">
        <div className="grid gap-4 md:grid-cols-3">
          <State label="static">
            <Card className="w-full">
              <CardHeader title="Brand kit" description="Fonts, colours and your channel intro." />
              <CardFooter>
                <Button size="sm" variant="secondary">
                  Edit
                </Button>
              </CardFooter>
            </Card>
          </State>
          <State label="interactive (link + menu)">
            <Card interactive className="w-full">
              <CardHeader
                title={
                  <Link href="#display" className={cx(cardLinkOverlay, 'hover:underline')}>
                    Founder podcast #12
                  </Link>
                }
                description="8 clips · 2 hours ago"
                actions={<IconButton label="Project actions" icon={<Ellipsis />} size="sm" />}
              />
              <div className="mt-3">
                <StatusBadge status="ready" />
              </div>
            </Card>
          </State>
          <State label="selected (toggle)">
            <Card selected={selected} className="w-full">
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => setSelected(!selected)}
                className={cx('w-full rounded-cn-md text-left', focusRing)}
              >
                <span className="block text-cn-title-sm font-semibold">Pro plan</span>
                <span className="block text-cn-body text-cn-fg-secondary">{selected ? 'Selected' : 'Click to select'}</span>
              </button>
            </Card>
          </State>
        </div>
      </Specimen>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="EmptyState" note="Say what is empty, why it matters, and the one next step.">
          <EmptyState
            icon={<FolderOpen />}
            title="No projects yet"
            description="Add a video or paste a link. Clipnera finds the best moments and cuts them into clips."
            action={<Button leadingIcon={<Upload />}>Add a video</Button>}
          />
          <div className="border-t border-cn-border">
            <EmptyState
              size="compact"
              level={3}
              icon={<Search />}
              title="No clips match “pricing”"
              description="Try fewer words, or search what was said instead of the title."
              action={
                <Button size="sm" variant="secondary">
                  Clear search
                </Button>
              }
            />
          </div>
        </Specimen>

        <Specimen title="Skeleton" note="Mirror the real layout. One status region per group, silent blocks. Pulse stops under reduced motion.">
          <SkeletonGroup label="Loading projects" className="space-y-4">
            {[0, 1].map((row) => (
              <div key={row} className="flex gap-3">
                <Skeleton className="aspect-[9/16] w-16 shrink-0" />
                <div className="flex-1 space-y-3 pt-1">
                  <Skeleton className="h-4 w-2/3" />
                  <SkeletonText lines={2} />
                </div>
              </div>
            ))}
          </SkeletonGroup>
        </Specimen>
      </div>

      <Specimen title="ProgressBar" note="Determinate whenever a number is known. Indeterminate sweeps; it never spins.">
        <div className="grid gap-5 md:grid-cols-2">
          <ProgressBar label="Uploading interview.mp4" value={42} />
          <ProgressBar label="Rendering 3 of 8 clips" value={3} max={8} valueText="3 of 8" />
          <ProgressBar label="Preparing preview" />
          <ProgressBar label="Export ready" value={100} tone="success" />
          <ProgressBar label="Upload stopped" value={64} tone="danger" valueText="Stopped at 64%" />
          <ProgressBar label="Storage used" value={18} size="sm" valueText="18 of 100 GB" />
        </div>
      </Specimen>

      <Specimen title="ProgressSteps" note="A fixed process with known stages. For an AI run, see StepList.">
        <div className="space-y-8">
          <ProgressSteps label="Project progress" steps={UPLOAD_STEPS} />
          <div className="grid gap-6 md:grid-cols-2">
            <ProgressSteps label="Project progress" steps={UPLOAD_STEPS} orientation="vertical" />
            <ProgressSteps label="Project progress, failed" steps={FAILED_STEPS} orientation="vertical" />
          </div>
        </div>
      </Specimen>
    </GallerySection>
  );
}
