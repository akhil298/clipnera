'use client';

import { Lock, MoreHorizontal, UserPlus, Users } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { Input } from '@/components/ui/Input';
import { Menu } from '@/components/ui/Menu';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';

import { Avatar, Callout, DataTable, RadioGroup, SelectField } from '../_components/Additions';
import { MockFrame } from '../_components/MockFrame';
import { SettingsCard, SettingsFrame } from '../_components/SettingsFrame';

const STATES = [
  { id: 'default', label: 'Owner, with team' },
  { id: 'empty', label: 'Only you' },
  { id: 'loading', label: 'Loading' },
  { id: 'error', label: 'Members failed to load' },
  { id: 'invite', label: 'Invite dialog' },
  { id: 'invite-error', label: 'Invite error' },
  { id: 'remove', label: 'Remove member' },
  { id: 'free', label: 'Free plan (locked)' },
  { id: 'member', label: 'Signed in as member' },
] as const;

type Role = 'member' | 'viewer';
interface Member { id: string; name: string; email: string; role: 'owner' | Role; status: 'active' | 'invited' }

const MEMBERS: Member[] = [
  { id: 'u1', name: 'Priya Sharma', email: 'priya.sharma@gmail.com', role: 'owner', status: 'active' },
  { id: 'u2', name: 'Arjun Mehta', email: 'arjun@studioframe.in', role: 'member', status: 'active' },
  { id: 'u3', name: 'Kavya Reddy', email: 'kavya.r@gmail.com', role: 'viewer', status: 'active' },
  { id: 'u4', name: 'rahul.k@gmail.com', email: 'rahul.k@gmail.com', role: 'member', status: 'invited' },
];

const ROLE_OPTIONS = [
  { value: 'member', label: 'Member', description: 'Edit projects, upload footage, export and publish.' },
  { value: 'viewer', label: 'Viewer', description: 'See projects and footage. Cannot edit, upload or publish.' },
] as const;

export function SettingsWorkspace() {
  return (
    <MockFrame title="Settings · Workspace and team" url="/dashboard/settings/workspace" flag="new_ui_settings" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const { show } = useToast();
  const [role, setRole] = useState<Role | null>('member');
  const owner = state !== 'member';
  const rows = state === 'empty' ? MEMBERS.slice(0, 1) : MEMBERS;

  return (
    <SettingsFrame section="workspace">
      <SettingsCard title="Workspace" description="Projects, uploads and brand kit belong to a workspace. Your plan and credits belong to you.">
        <div className="flex items-center gap-3">
          <Avatar name="Priya Studio" size={40} workspace />
          <div>
            <p className="text-cn-body font-semibold text-cn-fg">Priya's workspace</p>
            <p className="text-cn-caption text-cn-fg-muted">Personal · {rows.length} {rows.length === 1 ? 'person' : 'people'}</p>
          </div>
        </div>
      </SettingsCard>

      {state === 'free' ? (
        <SettingsCard title="Team" description="Invite people to work on your projects with you.">
          <Callout tone="neutral" title="Teams are part of Pro." action={<Button size="sm" leadingIcon={<Lock />}>See Pro</Button>}>
            On Pro you can invite people by their Google account and choose what each person can do.
          </Callout>
        </SettingsCard>
      ) : (
        <SettingsCard
          title="Team"
          description="People sign in with Google using the address you invite. No passwords."
          actions={owner && <Button leadingIcon={<UserPlus />} onClick={() => setState('invite')}>Invite someone</Button>}
        >
          {state === 'member' && (
            <Callout className="mb-4" tone="neutral">You're a member here. Only Priya Sharma (the owner) can invite people or change roles.</Callout>
          )}
          {state === 'loading' && (
            <SkeletonGroup label="Loading team" className="space-y-2">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
            </SkeletonGroup>
          )}
          {state === 'error' && (
            <Callout tone="danger" live="alert" title="Your team didn't load." action={<Button size="sm" variant="secondary">Try again</Button>}>
              Nobody's access has changed.
            </Callout>
          )}
          {state === 'empty' && (
            <EmptyState size="compact" icon={<Users />} level={3} title="Just you so far" description="Invite an editor or a client. They join with their Google account." />
          )}
          {!['loading', 'error'].includes(state) && (
            <DataTable
              caption="Team members"
              rows={rows}
              columns={[
                {
                  key: 'person', header: 'Person', primary: true,
                  render: (m) => (
                    <span className="flex items-center gap-2.5">
                      <Avatar name={m.name} size={32} />
                      <span className="min-w-0">
                        <span className="block truncate text-cn-body font-semibold text-cn-fg">{m.name}</span>
                        <span className="block truncate text-cn-caption text-cn-fg-muted">{m.email}</span>
                      </span>
                    </span>
                  ),
                },
                {
                  key: 'role', header: 'Role',
                  render: (m) => (m.role === 'owner' || !owner ? <span className="capitalize text-cn-fg-secondary">{m.role}</span> : (
                    <SelectField size="sm" label={`Role for ${m.name}`} hideLabel options={ROLE_OPTIONS.map((o) => ({ value: o.value, label: o.label, hint: o.description }))} value={m.role} onValueChange={(v) => show({ title: `${m.name} is now a ${v}`, tone: 'success' })} className="w-32" />
                  )),
                },
                { key: 'status', header: 'Status', render: (m) => (m.status === 'invited' ? <Badge tone="info">Invited · not joined yet</Badge> : <Badge tone="success">Active</Badge>) },
                {
                  key: 'actions', header: 'Actions', hideHeader: true,
                  render: (m) => (owner && m.role !== 'owner' ? (
                    <Menu
                      align="end"
                      items={[
                        { id: 'remove', label: m.status === 'invited' ? 'Cancel invite' : 'Remove from workspace', danger: true, onSelect: () => setState('remove') },
                      ]}
                      trigger={(props) => <IconButton {...props} size="sm" label={`More for ${m.name}`} icon={<MoreHorizontal />} />}
                    />
                  ) : null),
                },
              ]}
            />
          )}
        </SettingsCard>
      )}

      <Dialog
        open={state === 'invite' || state === 'invite-error'}
        onOpenChange={(o) => !o && setState('default')}
        title="Invite someone"
        description="They get an email with a link. They join by signing in with Google using this address."
        footer={<><Button variant="ghost" onClick={() => setState('default')}>Cancel</Button><Button onClick={() => { setState('default'); show({ title: 'Invite sent to rahul.k@gmail.com', tone: 'success' }); }}>Send invite</Button></>}
      >
        <div className="space-y-5">
          <Input
            label="Google account email"
            type="email"
            required
            data-autofocus
            defaultValue={state === 'invite-error' ? 'arjun@studioframe.in' : ''}
            placeholder="name@gmail.com"
            hint="Any Google account works, including Google Workspace addresses."
            error={state === 'invite-error' ? 'arjun@studioframe.in is already in this workspace.' : undefined}
          />
          <RadioGroup legend="What can they do?" options={ROLE_OPTIONS} value={role} onValueChange={setRole} />
        </div>
      </Dialog>

      <Dialog
        open={state === 'remove'}
        onOpenChange={(o) => !o && setState('default')}
        role="alertdialog"
        title="Remove Arjun Mehta?"
        description="Arjun loses access to this workspace's projects and uploads straight away. Projects he made stay here. His own account and plan aren't affected."
        footer={<><Button variant="ghost" onClick={() => setState('default')}>Keep Arjun</Button><Button variant="danger" onClick={() => setState('default')}>Remove Arjun</Button></>}
      />
    </SettingsFrame>
  );
}
