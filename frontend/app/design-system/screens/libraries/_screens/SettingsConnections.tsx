'use client';

import type { ReactNode } from 'react';
import { AlertTriangle, Lock, Plug, RefreshCw } from 'lucide-react';

import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';

import { Avatar, Callout, PlatformMark, type PlatformId, platformName } from '../_components/Additions';
import { MockFrame } from '../_components/MockFrame';
import { SettingsCard, SettingsFrame } from '../_components/SettingsFrame';

const STATES = [
  { id: 'default', label: 'Every account status' },
  { id: 'empty', label: 'Nothing connected' },
  { id: 'free', label: 'Free (1 account, at limit)' },
  { id: 'loading', label: 'Loading' },
  { id: 'error', label: 'Load failed' },
  { id: 'disconnect', label: 'Disconnect dialog' },
  { id: 'connected', label: 'Back from YouTube' },
  { id: 'cancelled', label: 'Connection cancelled' },
  { id: 'flag-off', label: 'Publishing switched off' },
] as const;

type AccountStatus = 'active' | 'expiring' | 'needs_reconnect' | 'disconnecting';
interface Account { id: string; platform: PlatformId; handle: string; audience: string; status: AccountStatus; note: string }

const ACCOUNTS: Account[] = [
  { id: 'a1', platform: 'youtube', handle: '@priyacooks', audience: '142.8K', status: 'active', note: 'Auto-disconnects 9 Oct, 4:30 pm.' },
  { id: 'a2', platform: 'youtube', handle: '@priya.shorts', audience: '8.1K', status: 'expiring', note: 'Auto-disconnects tomorrow, 11:00 am. Reconnect to keep posting for 7 more days.' },
  { id: 'a3', platform: 'instagram', handle: '@priya.cooks', audience: '51.2K', status: 'needs_reconnect', note: 'Access expired. Reconnect to keep publishing.' },
  { id: 'a4', platform: 'instagram', handle: '@priya.travels', audience: '3.4K', status: 'disconnecting', note: 'Removing Clipnera’s access and its stored tokens.' },
];

const STATUS: Record<AccountStatus, ReactNode> = {
  active: <Badge tone="success" dot>Active</Badge>,
  expiring: <Badge tone="accent" dot>Expiring soon</Badge>,
  needs_reconnect: <Badge tone="danger" dot>Needs reconnect</Badge>,
  disconnecting: <StatusBadge status="processing">Disconnecting</StatusBadge>,
};

export function SettingsConnections() {
  return (
    <MockFrame title="Settings · Connected accounts" url="/dashboard/settings/connections" flag="new_ui_settings (+ social_publishing)" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const { show } = useToast();
  const free = state === 'free';
  const accounts = state === 'empty' ? [] : free ? ACCOUNTS.slice(0, 1) : ACCOUNTS;
  const readOnly = state === 'flag-off';

  return (
    <SettingsFrame section="connections">
      {state === 'connected' && (
        <Callout tone="success" live="status" title="Connected @priyacooks on YouTube." action={<Button size="sm" variant="secondary">Back to Scheduler</Button>}>
          You can publish and schedule to it now.
        </Callout>
      )}
      {state === 'cancelled' && (
        <Callout tone="neutral" live="status" title="The connection was cancelled.">Nothing changed. Connect again whenever you're ready.</Callout>
      )}
      {readOnly && (
        <Callout tone="neutral" title="Publishing is switched off for now.">
          Scheduled posts are paused. You can still disconnect an account; nothing else changes.
        </Callout>
      )}

      <SettingsCard
        title="Publishing accounts"
        description="Clipnera posts only the clips you choose. Each account disconnects by itself 7 days after you connect or reconnect it; reconnecting takes a few seconds."
        actions={<span className="font-cn-mono text-cn-label tabular-nums text-cn-fg-muted">{accounts.length} of {free ? 1 : 4} accounts</span>}
      >
        {state === 'loading' && (
          <SkeletonGroup label="Loading accounts" className="space-y-3">
            <Skeleton className="h-24 rounded-cn-lg" />
            <Skeleton className="h-24 rounded-cn-lg" />
          </SkeletonGroup>
        )}
        {state === 'error' && (
          <Callout tone="danger" live="alert" title="Your connected accounts didn't load." action={<Button size="sm" variant="secondary">Try again</Button>}>
            Your accounts and scheduled posts haven't changed.
          </Callout>
        )}
        {state === 'empty' && (
          <EmptyState size="compact" level={3} icon={<Plug />} title="No accounts connected" description="Connect YouTube or Instagram to publish clips straight from Clipnera." />
        )}
        {!['loading', 'error'].includes(state) && (
          <div className="space-y-4">
            {(['youtube', 'instagram'] as const).map((platform) => {
              const list = accounts.filter((a) => a.platform === platform);
              const locked = free && platform === 'instagram';
              const atLimit = free && accounts.length >= 1;
              return (
                <section key={platform} aria-labelledby={`pl-${platform}`} className="rounded-cn-lg border border-cn-border">
                  <header className="flex flex-wrap items-center gap-3 border-b border-cn-border p-3">
                    <PlatformMark platform={platform} />
                    <h3 id={`pl-${platform}`} className="flex-1 text-cn-body font-semibold text-cn-fg">{platformName(platform)}</h3>
                    {!readOnly && (
                      <Button
                        size="sm"
                        variant="secondary"
                        leadingIcon={locked ? <Lock /> : undefined}
                        aria-disabled={atLimit && !locked ? true : undefined}
                        aria-describedby={atLimit ? `limit-${platform}` : undefined}
                      >
                        {locked ? 'Pro' : `Connect ${platformName(platform)}`}
                      </Button>
                    )}
                  </header>
                  {atLimit && !locked && <p id={`limit-${platform}`} className="px-3 pt-2 text-cn-caption text-cn-fg-muted">Free includes 1 account. Disconnect it or upgrade to add another.</p>}
                  {platform === 'instagram' && !free && <p className="px-3 pt-2 text-cn-caption text-cn-fg-muted">Instagram professional (creator or business) accounts only.</p>}
                  {list.length === 0 ? (
                    <p className="p-3 text-cn-label text-cn-fg-muted">Not connected.</p>
                  ) : (
                    <ul className="divide-y divide-cn-border">
                      {list.map((a) => (
                        <li key={a.id} className="flex flex-wrap items-start gap-3 p-3">
                          <Avatar name={a.handle.replace('@', '')} size={32} />
                          <div className="min-w-0 flex-1 space-y-1">
                            <p className="flex flex-wrap items-center gap-2 text-cn-body font-semibold text-cn-fg">
                              {a.handle} {STATUS[a.status]}
                            </p>
                            <p className="text-cn-caption text-cn-fg-muted"><span className="font-cn-mono">{a.audience}</span> audience</p>
                            <p className={a.status === 'needs_reconnect' || a.status === 'expiring' ? 'flex items-start gap-1.5 text-cn-label text-cn-fg' : 'text-cn-label text-cn-fg-muted'}>
                              {(a.status === 'needs_reconnect' || a.status === 'expiring') && <AlertTriangle aria-hidden className="mt-0.5 size-3.5 shrink-0 text-cn-accent-text" />}
                              {a.note}
                            </p>
                          </div>
                          <div className="flex gap-2">
                            {(a.status === 'needs_reconnect' || a.status === 'expiring') && !readOnly && (
                              <Button size="sm" leadingIcon={<RefreshCw />}>Reconnect</Button>
                            )}
                            <Button size="sm" variant="ghost" disabled={a.status === 'disconnecting'} onClick={() => setState('disconnect')}>
                              {a.status === 'disconnecting' ? 'Disconnecting' : 'Disconnect'}
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </SettingsCard>

      <Dialog
        open={state === 'disconnect'}
        onOpenChange={(o) => !o && setState('default')}
        role="alertdialog"
        title="Disconnect @priyacooks?"
        description="2 scheduled posts will be cancelled. Clipnera's access will be revoked and its stored tokens deleted."
        footer={
          <>
            <Button variant="ghost" onClick={() => setState('default')}>Keep connected</Button>
            <Button variant="danger" onClick={() => { setState('default'); show({ title: 'Disconnected @priyacooks', description: '2 scheduled posts cancelled.' }); }}>Disconnect</Button>
          </>
        }
      />
    </SettingsFrame>
  );
}
