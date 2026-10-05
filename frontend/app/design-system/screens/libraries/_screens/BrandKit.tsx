'use client';

import { CircleAlert, Lock } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Input } from '@/components/ui/Input';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';
import { Textarea } from '@/components/ui/Textarea';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx } from '@/lib/design/styles';

import { Callout, Dropzone, RadioGroup, SaveBar, SelectField } from '../_components/Additions';
import { MockFrame } from '../_components/MockFrame';
import { Poster } from '../_components/Media';
import { AppShell, PageBody, ScreenHeader } from '../_components/Shells';
import { SettingsCard } from '../_components/SettingsFrame';

const STATES = [
  { id: 'default', label: 'Saved kit' },
  { id: 'dirty', label: 'Unsaved changes' },
  { id: 'saving', label: 'Saving' },
  { id: 'invalid', label: 'Invalid colour' },
  { id: 'leave', label: 'Leave with unsaved changes' },
  { id: 'loading', label: 'Loading' },
  { id: 'load-failed', label: 'Load failed (form hidden)' },
  { id: 'free', label: 'Free plan' },
  { id: 'intro-rendering', label: 'Intro: creating' },
  { id: 'intro-ready', label: 'Intro: ready' },
  { id: 'intro-failed', label: 'Intro: failed' },
] as const;

const POSITIONS = [
  { value: 'top-left', label: 'Top left' },
  { value: 'top-right', label: 'Top right' },
  { value: 'bottom-left', label: 'Bottom left' },
  { value: 'bottom-right', label: 'Bottom right' },
] as const;

const FONTS = [
  { value: 'Syne', label: <span className="font-cn-display text-cn-title font-bold">Aa</span>, description: 'Syne · Ultra bold' },
  { value: 'Plus Jakarta Sans', label: <span className="font-cn-sans text-cn-title font-bold">Aa</span>, description: 'Plus Jakarta Sans · Clean' },
  { value: 'JetBrains Mono', label: <span className="font-cn-mono text-cn-title font-bold">Aa</span>, description: 'JetBrains Mono · Techy' },
] as const;

const PRESETS = ['Spotlight', 'Karaoke pop', 'Clean lower', 'Bold block', 'Neon edge', 'Typewriter'] as const;

const INTRO_PLATFORMS = ['YouTube', 'Instagram', 'TikTok', 'Twitch', 'X', 'Facebook', 'Kick', 'LinkedIn', 'Other'].map((p) => ({ value: p, label: p }));

export function BrandKit() {
  return (
    <MockFrame title="Brand kit (with channel intro)" url="/dashboard/brand-kit" flag="new_ui_settings" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const [position, setPosition] = useState<(typeof POSITIONS)[number]['value']>('bottom-right');
  const [font, setFont] = useState<string>('Plus Jakarta Sans');
  const [preset, setPreset] = useState<string>('Spotlight');
  const [platform, setPlatform] = useState<string>('YouTube');
  const [look, setLook] = useState<'auto' | 'light' | 'dark'>('auto');
  const free = state === 'free';
  const dirty = ['dirty', 'saving', 'invalid', 'leave'].includes(state);

  if (state === 'loading' || state === 'load-failed') {
    return (
      <AppShell active="brand-kit">
        <PageBody>
          <ScreenHeader title="Brand kit" description="Applied to every new clip: watermark, fonts, colours, default caption style and your channel intro." />
          {state === 'loading' ? (
            <SkeletonGroup label="Loading your brand kit" className="grid gap-6 lg:grid-cols-12">
              <Skeleton className="h-96 rounded-cn-lg lg:col-span-7" />
              <Skeleton className="h-96 rounded-cn-lg lg:col-span-5" />
            </SkeletonGroup>
          ) : (
            <EmptyState
              icon={<CircleAlert />}
              title="Your brand kit didn't load"
              description="Your saved kit is safe. We don't show the form until it loads, so nothing can be overwritten by mistake."
              action={<Button>Try again</Button>}
            />
          )}
        </PageBody>
      </AppShell>
    );
  }

  return (
    <AppShell active="brand-kit">
      <PageBody>
        <ScreenHeader title="Brand kit" description="Applied to every new clip: watermark, fonts, colours, default caption style and your channel intro." />
        {free && (
          <Callout tone="neutral" title="Editing your brand kit is part of Pro." action={<Button size="sm" leadingIcon={<Lock />}>See Pro</Button>}>
            You can try every setting and see it in the preview. Saving opens the plan options.
          </Callout>
        )}
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-7">
            <SettingsCard title="Identity and watermark">
              <div className="space-y-5">
                <Input label="Brand or channel name" defaultValue="Priya Cooks" placeholder="e.g. Clipnera" />
                <div className="space-y-2">
                  <p className="text-cn-label font-semibold text-cn-fg">Logo</p>
                  <Dropzone compact title="Add your logo" hint="PNG or SVG with a transparent background, up to 2 MB. Without one, your brand name is used." accept="image/png,image/svg+xml" />
                </div>
                <RadioGroup legend="Watermark position" layout="cards" options={POSITIONS} value={position} onValueChange={setPosition} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="space-y-1.5">
                    <span className="flex justify-between text-cn-label font-semibold text-cn-fg">Opacity <span className="font-cn-mono font-normal text-cn-fg-secondary">80%</span></span>
                    <input type="range" min={20} max={100} defaultValue={80} aria-valuetext="80 percent" className="block h-6 w-full accent-cn-accent" />
                  </label>
                  <label className="space-y-1.5">
                    <span className="flex justify-between text-cn-label font-semibold text-cn-fg">Size <span className="font-cn-mono font-normal text-cn-fg-secondary">28 px</span></span>
                    <input type="range" min={18} max={48} defaultValue={28} aria-valuetext="28 pixels" className="block h-6 w-full accent-cn-accent" />
                  </label>
                </div>
              </div>
            </SettingsCard>

            <SettingsCard title="Type and colour">
              <div className="space-y-5">
                <RadioGroup legend="Font" layout="cards" options={FONTS} value={font} onValueChange={setFont} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Highlight colour"
                    hint="The active word in captions."
                    defaultValue={state === 'invalid' ? '#ffcc0' : '#F59E0B'}
                    error={state === 'invalid' ? 'Use a 6-digit hex colour, like #F59E0B.' : undefined}
                    leading={<span aria-hidden className="size-4 rounded-cn-xs border border-cn-border" style={{ background: '#F59E0B' }} />}
                    className="font-cn-mono"
                  />
                  <Input label="Accent colour" hint="Supporting text and details." defaultValue="#FAFAFA" leading={<span aria-hidden className="size-4 rounded-cn-xs border border-cn-border" style={{ background: '#FAFAFA' }} />} />
                </div>
              </div>
            </SettingsCard>

            <SettingsCard title="Default caption style" description="New clips start with this style. You can change it per clip.">
              <RadioGroup
                legend="Caption style"
                hideLegend
                layout="cards"
                options={PRESETS.map((p, i) => ({ value: p, label: p, description: i < 2 ? 'Free and Pro' : 'Pro' }))}
                value={preset}
                onValueChange={setPreset}
              />
            </SettingsCard>

            <SettingsCard title="Extras">
              <div className="space-y-4">
                <Checkbox defaultChecked label="Auto emojis in captions" description='Adds a matching emoji to words like "secret", "money" or "rocket".' />
                <Input label="End card call to action" placeholder="e.g. Follow @yourbrand for daily breakdowns" defaultValue="Follow @priyacooks for a recipe a day" />
              </div>
            </SettingsCard>

            <SettingsCard
              id="channel-intro"
              title={<span className="inline-flex items-center gap-2">Channel intro {free && <Badge tone="accent" icon={<Lock />}>Pro</Badge>}</span>}
              description="A 6-second intro with your name, what your channel is about, and a cursor tapping your platform's Like and Subscribe or Follow. Made once, then played before every clip you export."
              actions={state === 'intro-ready' && <Switch defaultChecked label="Play before every export" />}
            >
              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-4">
                  <SelectField label="Platform" options={INTRO_PLATFORMS} value={platform} onValueChange={setPlatform} />
                  <Input label="Channel name" required defaultValue="Priya Cooks" placeholder="e.g. Sreekanth Go" />
                  <Input label="Handle (optional)" defaultValue="@priyacooks" />
                  <Textarea label="What's your channel about?" defaultValue="Quick vegetarian recipes for busy weeknights." maxLength={300} showCount />
                  <Input label="Line shown in the intro" placeholder="Leave empty and AI writes it from the description above" hint="Clear it to have the AI write a new one." />
                  <SegmentedControl label="Look" options={[{ value: 'auto', label: 'Auto' }, { value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]} value={look} onValueChange={setLook} />
                  <Button disabled={state === 'intro-rendering'} variant="secondary">
                    {state === 'intro-ready' || state === 'intro-failed' ? 'Re-create intro' : 'Create intro'} · uses 1 of 5 intro renders today
                  </Button>
                </div>
                <div className="space-y-2">
                  <p className="text-cn-label font-semibold text-cn-fg">Preview</p>
                  <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-cn-lg border border-cn-border bg-cn-surface-hover p-4 text-center">
                    {state === 'intro-rendering' && <WorkingText>Writing and creating your intro</WorkingText>}
                    {state === 'intro-ready' && <><Poster look={['#0a0a0a', '#f59e0b', '#171717']} className="absolute inset-0" /><span data-theme="dark" className="relative text-cn-title-sm font-bold text-cn-fg">Priya Cooks</span></>}
                    {state === 'intro-failed' && <p className="text-cn-label text-cn-danger-text">The intro didn't finish. Your settings are saved and nothing was used. Try again.</p>}
                    {!state.startsWith('intro') && <p className="text-cn-label text-cn-fg-muted">Your intro shows here once it's created.</p>}
                  </div>
                  {state === 'intro-ready' && <p className="text-cn-caption text-cn-fg-muted">Showing: "Weeknight veg in 10 minutes" · Dark look</p>}
                </div>
              </div>
            </SettingsCard>
          </div>

          <aside aria-label="Preview" className="lg:col-span-5">
            <div className="space-y-2 lg:sticky lg:top-6">
              <p className="flex justify-between text-cn-label text-cn-fg-secondary">Preview <span className="font-cn-mono text-cn-caption text-cn-fg-muted">9:16 · {preset}</span></p>
              <div data-theme="dark" className="relative mx-auto w-64 overflow-hidden rounded-cn-xl border-4 border-cn-border-strong" style={{ aspectRatio: '9 / 16' }}>
                <Poster look={['#3b2a1a', '#f59e0b', '#0a0a0a']} className="absolute inset-0" />
                <span className={cx('absolute rounded-cn-sm bg-cn-bg/70 px-2 py-1 text-cn-caption font-semibold text-cn-fg', position.includes('top') ? 'top-3' : 'bottom-16', position.includes('left') ? 'left-3' : 'right-3')} style={{ opacity: 0.8 }}>
                  Priya Cooks
                </span>
                <p className="absolute inset-x-4 top-1/2 text-center text-cn-title font-bold uppercase leading-tight text-cn-fg" style={{ fontFamily: font }}>
                  The easiest <span style={{ color: '#F59E0B' }}>dal</span> you'll ever make
                </p>
                <span className="absolute inset-x-6 bottom-4 rounded-cn-full bg-cn-bg/70 py-1 text-center text-cn-caption text-cn-fg">Follow @priyacooks for a recipe a day</span>
              </div>
            </div>
          </aside>
        </div>
      </PageBody>
      <SaveBar show={dirty}>
        <span aria-hidden className="size-2 rounded-cn-full bg-cn-accent" />
        <p className="flex-1 text-cn-body text-cn-fg">Unsaved changes</p>
        <Button variant="ghost" onClick={() => setState('default')}>Discard</Button>
        <Button loading={state === 'saving'} loadingLabel="Saving" leadingIcon={free ? <Lock /> : undefined} onClick={() => setState('saving')}>
          Save brand kit
        </Button>
      </SaveBar>
      <Dialog
        open={state === 'leave'}
        onOpenChange={(o) => !o && setState('dirty')}
        role="alertdialog"
        title="Leave without saving?"
        description="Your changes to the brand kit will be lost. Your saved kit stays as it was."
        footer={<><Button variant="ghost" onClick={() => setState('dirty')}>Keep editing</Button><Button variant="secondary" onClick={() => setState('default')}>Leave without saving</Button></>}
      />
    </AppShell>
  );
}
