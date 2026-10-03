'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';

import { Callout, SelectField } from '../_components/Additions';
import { MockFrame } from '../_components/MockFrame';
import { SettingsCard, SettingsFrame } from '../_components/SettingsFrame';

const STATES = [
  { id: 'default', label: 'Default' },
  { id: 'saved', label: 'Saved (status line)' },
  { id: 'save-failed', label: 'Save failed (reverted)' },
  { id: 'unsubscribed', label: 'Unsubscribed by email link' },
  { id: 'browser-denied', label: 'Browser blocked notifications' },
  { id: 'loading', label: 'Loading' },
] as const;

const THRESHOLDS = [
  { value: '60', label: 'Longer than 1 minute' },
  { value: '300', label: 'Longer than 5 minutes', hint: 'Default' },
  { value: '900', label: 'Longer than 15 minutes' },
  { value: '1800', label: 'Longer than 30 minutes' },
] as const;

export function SettingsNotifications() {
  return (
    <MockFrame title="Settings · Notifications" url="/dashboard/settings/notifications" flag="new_ui_settings" states={STATES}>
      {(state) => <Body state={state} />}
    </MockFrame>
  );
}

/** Switches apply immediately (02 §3.7). One polite status line under each card says what was saved. */
function Body({ state }: { state: string }) {
  const [completion, setCompletion] = useState(true);
  const [after, setAfter] = useState<string>('300');
  const [account, setAccount] = useState(state !== 'unsubscribed');
  const [browser, setBrowser] = useState(false);

  if (state === 'loading') {
    return (
      <SettingsFrame section="notifications">
        <SkeletonGroup label="Loading notification settings" className="space-y-4">
          <Skeleton className="h-40 rounded-cn-lg" />
          <Skeleton className="h-28 rounded-cn-lg" />
        </SkeletonGroup>
      </SettingsFrame>
    );
  }

  return (
    <SettingsFrame section="notifications">
      <p className="text-cn-body text-cn-fg-secondary">You always get an in-app notification and a toast when an upload, edit or export finishes. Choose what else reaches you.</p>

      <SettingsCard title="When long work finishes" description="Clipnera keeps working when you close the tab. We can tell you when it's done.">
        <div className="space-y-5">
          <Switch checked={completion} onCheckedChange={setCompletion} label="Email me when it finishes" description="For uploads, edits and exports that take a while." />
          <SelectField label="Only for jobs" options={THRESHOLDS} value={after} onValueChange={setAfter} disabled={!completion} className="max-w-xs" />
          <Switch
            checked={browser}
            onCheckedChange={setBrowser}
            disabled={state === 'browser-denied'}
            label="Show a browser notification"
            description={state === 'browser-denied' ? 'Your browser is blocking notifications from Clipnera. Allow them in the site settings, then come back.' : 'Your browser asks for permission the first time.'}
          />
        </div>
        {state === 'saved' && <p role="status" className="mt-4 text-cn-label text-cn-success-text">Saved. Emails go to priya.sharma@gmail.com.</p>}
        {state === 'save-failed' && (
          <Callout className="mt-4" tone="danger" live="alert" title="That change didn't save." action={<Button size="sm" variant="secondary">Try again</Button>}>
            We put the switch back. Your other settings are unchanged.
          </Callout>
        )}
      </SettingsCard>

      <SettingsCard title="Account emails" description="Emails when a scheduled post fails or a connected account needs reconnecting. We never send marketing emails.">
        {state === 'unsubscribed' && <Callout className="mb-4" tone="neutral">You turned these off from an email link. Turn them back on here any time.</Callout>}
        <Switch checked={account} onCheckedChange={setAccount} label="Account emails" />
      </SettingsCard>
    </SettingsFrame>
  );
}
