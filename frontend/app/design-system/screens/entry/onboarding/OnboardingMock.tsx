'use client';

import { CircleAlert, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Chip } from '@/components/ui/Chip';
import { Dialog } from '@/components/ui/Dialog';

import { AppShell } from '../_mock/AppShell';
import { ENTRY_BASE } from '../_mock/data';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { SCREENS } from '../_mock/states';

const MAKE = ['Podcasts', 'Interviews', 'Talking-head videos', 'Tutorials and courses', 'Streams and gaming', 'Vlogs', 'Webinars and talks', 'Something else'];
const POST = ['YouTube Shorts', 'Instagram Reels', 'Somewhere else', 'Not posting yet'];

export function OnboardingMock({ state, theme }: { state: string; theme?: string }) {
  const step = state === 'step-1' ? 1 : 2;
  const [open, setOpen] = useState(state !== 'carried');
  const [made, setMade] = useState<string[]>(['Podcasts', 'Interviews']);
  const [posted, setPosted] = useState<string[]>(state === 'step-1' ? [] : ['YouTube Shorts', 'Instagram Reels']);
  const options = step === 1 ? MAKE : POST;
  const picked = step === 1 ? made : posted;
  const setPicked = step === 1 ? setMade : setPosted;
  const toggle = (value: string) => setPicked((cur) => (cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value]));

  return (
    <ScreenFrame
      screen={SCREENS.onboarding.title}
      states={SCREENS.onboarding.states}
      state={state}
      theme={theme}
      note="Shown once per account, over Home, only when no prompt was carried in. Every step can be skipped; answers tune Home's suggestions and default formats and can be changed in Settings."
    >
      <AppShell active="home" crumbs={[{ label: 'Home' }]} hidePromptEntry jobs={[]}>
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-4 py-12 text-center">
          <p className="text-cn-label text-cn-fg-secondary">Welcome to Clipnera, Akhil</p>
          <h1 className="text-cn-display-sm font-bold md:text-cn-display">What should we cut today?</h1>
          {state === 'carried' && (
            <Card className="mt-6 flex w-full flex-wrap items-center gap-3 text-left">
              <Sparkles aria-hidden className="size-4 text-cn-accent-text" />
              <p className="flex-1 text-cn-label text-cn-fg-secondary">
                You came in with a prompt, so I skipped the welcome questions. I’ll ask them here after your first clips are ready.
              </p>
              <Link href={`${ENTRY_BASE}/home?state=restored`} className="text-cn-label text-cn-accent-text underline">
                See Home with the prompt
              </Link>
            </Card>
          )}
        </div>

        <Dialog
          open={open}
          onOpenChange={setOpen}
          size="md"
          title={step === 1 ? 'What do you make?' : 'Where do you post?'}
          description={
            step === 1
              ? `Step 1 of 2. Pick any that fit; I’ll suggest prompts for them.`
              : 'Step 2 of 2. I’ll set your default format. You can publish straight to YouTube and Instagram from Clipnera.'
          }
          dismissible={state !== 'saving'}
          footer={
            <>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                Skip
              </Button>
              <Button loading={state === 'saving'} loadingLabel="Saving" onClick={() => setOpen(false)}>
                {step === 1 ? 'Next' : 'Start making clips'}
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <div role="group" aria-label={step === 1 ? 'What you make' : 'Where you post'} className="flex flex-wrap gap-2">
              {options.map((option) => (
                <Chip key={option} selected={picked.includes(option)} onClick={() => toggle(option)}>
                  {option}
                </Chip>
              ))}
            </div>
            {step === 2 && (
              <p className="text-cn-caption text-cn-fg-muted">You have 20 free credits, about 10 minutes of video. Free credits renew every 30 days.</p>
            )}
            {state === 'error' && (
              <p role="alert" className="flex items-start gap-1.5 text-cn-label text-cn-danger-text">
                <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
                I couldn’t save your answers. You can carry on; I’ll ask again next time.
              </p>
            )}
          </div>
        </Dialog>
      </AppShell>
    </ScreenFrame>
  );
}
