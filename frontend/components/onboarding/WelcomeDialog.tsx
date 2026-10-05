'use client';

import Link from 'next/link';
import { useState } from 'react';

import { PROMPT_FOCUS_EVENT } from '@/components/shell';
import { Button, buttonClasses, Chip, Dialog } from '@/components/ui';

import { ConnectStep } from './ConnectStep';
import { CREATOR_TYPES, saveOnboarding, type CreatorType } from './preferences';

const UPLOAD_HREF = '/dashboard/upload';

const STEPS = [
  { title: 'What do you make?', description: 'Step 1 of 3. Pick any that fit; I’ll suggest prompts for them.' },
  { title: 'Connect a channel', description: 'Step 2 of 3. Optional. Publish straight to YouTube and Instagram from Clipnera. You can do this later in Settings.' },
  { title: 'Add your first video', description: 'Step 3 of 3. Paste a YouTube link into the box on Home, or upload a file. Nothing runs until you press send.' },
] as const;

export interface WelcomeDialogProps {
  open: boolean;
  /** Called after the answers are saved, however the person left (finish, Skip, Escape, connect). */
  onClose: () => void;
  userId: string;
  /** From GET /me; the line is left out when unknown, never guessed. */
  creditMinutes: number | null;
}

/** First-run welcome over Home (screens/01 §4): three short steps, every one skippable, shown once. */
export function WelcomeDialog({ open, onClose, userId, creditMinutes }: WelcomeDialogProps) {
  const [step, setStep] = useState(0);
  const [picked, setPicked] = useState<CreatorType[]>([]);
  const { title, description } = STEPS[step];
  const last = step === STEPS.length - 1;

  // Skipping counts as done: the welcome never comes back for this account on this device.
  const finish = () => {
    saveOnboarding(userId, picked);
    onClose();
  };

  const startWithPrompt = () => {
    finish();
    // Home's composer takes focus; elsewhere the shell opens its prompt entry.
    window.dispatchEvent(new Event(PROMPT_FOCUS_EVENT, { cancelable: true }));
  };

  const toggle = (type: CreatorType) => setPicked((current) => (current.includes(type) ? current.filter((item) => item !== type) : [...current, type]));

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && finish()}
      size="md"
      title={title}
      description={description}
      footer={
        <>
          <Button variant="ghost" onClick={finish}>
            Skip
          </Button>
          {step > 0 && (
            <Button variant="ghost" onClick={() => setStep(step - 1)}>
              Back
            </Button>
          )}
          <Button onClick={last ? startWithPrompt : () => setStep(step + 1)}>{last ? 'Start making clips' : 'Next'}</Button>
        </>
      }
    >
      {step === 0 && (
        <div role="group" aria-label="What you make" className="flex flex-wrap gap-2">
          {CREATOR_TYPES.map((type, index) => (
            <Chip key={type} selected={picked.includes(type)} onClick={() => toggle(type)} data-autofocus={index === 0 || undefined}>
              {type}
            </Chip>
          ))}
        </div>
      )}
      {step === 1 && <ConnectStep onLeave={() => saveOnboarding(userId, picked)} />}
      {step === 2 && (
        <div className="flex flex-col gap-4">
          {/* Saves without closing: the navigation replaces this dialog (and Home) itself. */}
          <Link href={UPLOAD_HREF} onClick={() => saveOnboarding(userId, picked)} className={buttonClasses({ variant: 'secondary', fullWidth: true })}>
            Upload a file instead
          </Link>
          {creditMinutes !== null && (
            <p className="text-cn-caption text-cn-fg-muted">
              You have {creditMinutes} {creditMinutes === 1 ? 'minute' : 'minutes'} of video credits.
            </p>
          )}
        </div>
      )}
    </Dialog>
  );
}
