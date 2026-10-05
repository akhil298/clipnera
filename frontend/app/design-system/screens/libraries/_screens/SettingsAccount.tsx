'use client';

import { Crown, LogOut, Monitor, Smartphone } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Skeleton, SkeletonGroup, SkeletonText } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';

import { Avatar, Callout, KeyValues } from '../_components/Additions';
import { MockFrame } from '../_components/MockFrame';
import { SettingsCard, SettingsFrame } from '../_components/SettingsFrame';

const STATES = [
  { id: 'default', label: 'Default' },
  { id: 'loading', label: 'Loading' },
  { id: 'error', label: 'Load failed' },
  { id: 'delete', label: 'Delete dialog' },
  { id: 'delete-typed', label: 'Delete, email typed' },
  { id: 'deleting', label: 'Deleting' },
  { id: 'delete-error', label: 'Delete failed' },
  { id: 'sessions-off', label: 'Before auth hardening ships' },
] as const;

const EMAIL = 'priya.sharma@gmail.com';

export function SettingsAccount() {
  return (
    <MockFrame title="Settings · Account and privacy" url="/dashboard/settings/account" flag="new_ui_settings" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const [typed, setTyped] = useState('');
  const value = state === 'delete-typed' || state === 'deleting' || state === 'delete-error' ? EMAIL : typed;
  const matches = value.trim().toLowerCase() === EMAIL;
  const dialogOpen = state.startsWith('delet');

  if (state === 'loading') {
    return (
      <SettingsFrame section="account">
        <SkeletonGroup label="Loading your account" className="space-y-4">
          <Skeleton className="h-32 w-full rounded-cn-lg" />
          <SkeletonText lines={4} />
        </SkeletonGroup>
      </SettingsFrame>
    );
  }

  return (
    <SettingsFrame section="account">
      {state === 'error' && (
        <Callout tone="danger" live="alert" title="Your account details didn't load." action={<Button size="sm" variant="secondary">Try again</Button>}>
          Nothing has changed. Settings you can't see aren't editable until they load.
        </Callout>
      )}
      <SettingsCard title="Profile" description="Your name, email and picture come from your Google account. Change them in Google and they update here at your next sign-in.">
        <div className="flex flex-wrap items-center gap-4">
          <Avatar name="Priya Sharma" size={40} />
          <div className="min-w-0 flex-1">
            <p className="text-cn-body font-semibold text-cn-fg">Priya Sharma</p>
            <p className="text-cn-label text-cn-fg-muted">{EMAIL}</p>
          </div>
          <Badge tone="accent" icon={<Crown />}>Pro plan</Badge>
        </div>
        <KeyValues className="mt-4" items={[{ label: 'Signed in with', value: 'Google' }, { label: 'Member since', value: '14 Jun 2026' }, { label: 'Age confirmed', value: '18 or older · 14 Jun 2026' }]} />
      </SettingsCard>

      <SettingsCard title="Privacy" description="Choices about how Clipnera uses what you upload.">
        <Switch
          defaultChecked
          label="Use my uploads in AI edits"
          description="When you ask for B-roll, Clipnera may pick shots from your own uploads, and tells you when it does. Turn off to use only the Clipnera library."
        />
      </SettingsCard>

      {state !== 'sessions-off' && (
        <SettingsCard title="Where you're signed in" description="Sign out of a device you don't recognise. Signing out everywhere else keeps this device signed in." actions={<Button size="sm" variant="secondary" leadingIcon={<LogOut />}>Sign out everywhere else</Button>}>
          <ul className="divide-y divide-cn-border">
            {[
              { icon: <Monitor />, name: 'Chrome on macOS', where: 'Hyderabad · active now', current: true },
              { icon: <Smartphone />, name: 'Safari on iPhone', where: 'Hyderabad · 2 days ago' },
              { icon: <Monitor />, name: 'Edge on Windows', where: 'Bengaluru · 9 Sep' },
            ].map((s) => (
              <li key={s.name} className="flex items-center gap-3 py-3">
                <span aria-hidden className="text-cn-fg-muted [&_svg]:size-4">{s.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-cn-body text-cn-fg">{s.name} {s.current && <Badge tone="success">This device</Badge>}</p>
                  <p className="text-cn-caption text-cn-fg-muted">{s.where}</p>
                </div>
                {!s.current && <Button size="sm" variant="ghost">Sign out</Button>}
              </li>
            ))}
          </ul>
        </SettingsCard>
      )}

      <SettingsCard
        danger
        title="Delete account"
        description={
          <>
            Permanently deletes your account, videos, clips, reels, brand kits, payment records and connected social accounts. Unused credits and any paid time left are lost. This cannot be undone. See the{' '}
            <a href="/privacy" className="text-cn-accent-text underline underline-offset-2">privacy policy</a>.
          </>
        }
        actions={<Button variant="secondary" className="text-cn-danger-text" onClick={() => setState('delete')}>Delete account…</Button>}
      />

      <Dialog
        open={dialogOpen}
        onOpenChange={(o) => !o && setState('default')}
        role="alertdialog"
        dismissible={state !== 'deleting'}
        title="Delete your account?"
        description="Your account, videos, clips, reels, brand kits, payment records and connected social accounts are deleted immediately and permanently. Unused credits and any paid time left are lost."
        footer={
          <>
            <Button variant="ghost" disabled={state === 'deleting'} onClick={() => setState('default')}>Keep my account</Button>
            <Button variant="danger" disabled={!matches} loading={state === 'deleting'} loadingLabel="Deleting" onClick={() => setState('deleting')}>
              Permanently delete my account
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Callout tone="warning" title="You have 22 days of Pro left and 140 pack credits.">They end with the account. Payments already made aren't refunded.</Callout>
          <Input
            label={<>Type <b className="font-cn-mono">{EMAIL}</b> to confirm</>}
            value={value}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            data-autofocus
            error={state === 'delete-error' ? "Your account wasn't deleted: we couldn't remove your stored files. Nothing was lost. Try again." : undefined}
          />
        </div>
      </Dialog>
    </SettingsFrame>
  );
}
