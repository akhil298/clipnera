'use client';

import Link from 'next/link';
import { useState } from 'react';

import { PROMPT_FOCUS_EVENT } from '@/components/shell';
import { Button, buttonClasses, Dialog, InlineAlert } from '@/components/ui';
import { isApiError } from '@/lib/api/errors';
import { ONBOARDING_ROLES, ONBOARDING_SOURCES } from '@/lib/types';

import { ChoiceStep } from './ChoiceStep';
import { ConnectStep } from './ConnectStep';
import { ReferralCodeStep } from './ReferralCodeStep';
import { useWelcomeForm } from './useWelcomeForm';

const UPLOAD_HREF = '/dashboard/upload';

type StepId = 'role' | 'source' | 'code' | 'connect' | 'start';

const COPY: Record<StepId, { title: string; description: string }> = {
  role: { title: 'What best describes you?', description: 'Pick the one that fits best.' },
  source: { title: 'How did you hear about us?', description: 'It helps us know what’s working.' },
  code: { title: 'Have a referral code?', description: 'Optional. A friend’s code can earn you bonus credits.' },
  connect: { title: 'Connect a channel', description: 'Optional. Publish straight to YouTube and Instagram from Clipnera. You can do this later in Settings.' },
  start: { title: 'Add your first video', description: 'Paste a YouTube link into the box on Home, or upload a file. Nothing runs until you press send.' },
};

export interface WelcomeDialogProps {
  open: boolean;
  /** Called however the person left. Before the form is sent, the welcome comes back on the next visit to Home. */
  onClose: () => void;
  /** `onboarding_completed` from GET /me: the form steps are left out once it is sent. */
  formDone: boolean;
  /** From GET /me; the line is left out when unknown, never guessed. */
  creditMinutes: number | null;
}

/**
 * First-run welcome over Home (screens/01 §4). The required form (role, how
 * they heard, optional referral code) is saved with `POST /onboarding`, the
 * same answers the legacy welcome form asks for; connecting a channel and
 * adding a first video follow and can be skipped.
 */
export function WelcomeDialog({ open, onClose, formDone, creditMinutes }: WelcomeDialogProps) {
  const form = useWelcomeForm();
  const sent = formDone || form.submit.isSuccess;
  const steps: readonly StepId[] = sent ? ['connect', 'start'] : ['role', 'source', ...(form.canUseCode ? (['code'] as const) : [])];
  const [index, setIndex] = useState(0);
  const step = steps[Math.min(index, steps.length - 1)];
  const last = index >= steps.length - 1;

  const startWithPrompt = () => {
    onClose();
    // Home's composer takes focus; elsewhere the shell opens its prompt entry.
    window.dispatchEvent(new Event(PROMPT_FOCUS_EVENT, { cancelable: true }));
  };
  const send = (withCode: boolean) => form.submit.mutate(withCode, { onSuccess: () => setIndex(0) });
  const primary = () => {
    if (sent && last) return startWithPrompt();
    if (last) return send(true);
    setIndex(index + 1);
  };

  const ready = step === 'role' ? form.roleReady : step === 'source' ? form.sourceReady : step === 'code' ? form.codeReady : true;
  const { title, description } = COPY[step];

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => !nextOpen && onClose()}
      dismissible={!form.submit.isPending}
      size="md"
      title={title}
      description={`Step ${index + 1} of ${steps.length}. ${description}`}
      footer={
        <>
          {step === 'code' && (
            <Button variant="ghost" disabled={form.submit.isPending} onClick={() => send(false)}>
              Skip
            </Button>
          )}
          {sent && !last && (
            <Button variant="ghost" onClick={onClose}>
              Skip
            </Button>
          )}
          {index > 0 && (
            <Button variant="ghost" disabled={form.submit.isPending} onClick={() => setIndex(index - 1)}>
              Back
            </Button>
          )}
          <Button onClick={primary} disabled={!ready} loading={form.submit.isPending}>
            {!last ? 'Next' : sent ? 'Start making clips' : 'Finish'}
          </Button>
        </>
      }
    >
      {step === 'role' && (
        <ChoiceStep
          label="What best describes you"
          options={ONBOARDING_ROLES}
          selected={form.role}
          onSelect={form.setRole}
          otherLabel="Tell us what you do"
          other={form.roleOther}
          onOtherChange={form.setRoleOther}
        />
      )}
      {step === 'source' && (
        <ChoiceStep
          label="How you heard about us"
          options={ONBOARDING_SOURCES}
          selected={form.source}
          onSelect={form.setSource}
          otherLabel="Where did you hear about us?"
          other={form.sourceOther}
          onOtherChange={form.setSourceOther}
        />
      )}
      {step === 'code' && <ReferralCodeStep form={form} />}
      {form.submit.isError && (
        <InlineAlert tone="danger" className="mt-4">
          {isApiError(form.submit.error) ? form.submit.error.message : 'Couldn’t save your answers. Try again.'}
        </InlineAlert>
      )}
      {step === 'connect' && <ConnectStep />}
      {step === 'start' && (
        <div className="flex flex-col gap-4">
          {/* The navigation replaces this dialog (and Home) itself. */}
          <Link href={UPLOAD_HREF} className={buttonClasses({ variant: 'secondary', fullWidth: true })}>
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
