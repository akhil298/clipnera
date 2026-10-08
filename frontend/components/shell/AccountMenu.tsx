'use client';

import { Gift, LogOut, RotateCcw, Settings, ShieldCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { AvatarMenu, IconButton, type MenuEntry, Skeleton } from '@/components/ui';
import { cx } from '@/lib/design/styles';

import { ADMIN_HREF, REFERRALS_HREF, SETTINGS_HREF } from './nav';
import { type ThemeChoice, useShell } from './ShellContext';
import { planName, useMe, useWorkspaces } from './useAccount';
import { useSignOut } from './useSignOut';

const THEMES: ReadonlyArray<{ id: ThemeChoice; label: string }> = [
  { id: 'dark', label: 'Dark' },
  { id: 'light', label: 'Light' },
  { id: 'system', label: 'Match system' },
];

export interface AccountMenuProps {
  /** Avatar only: the collapsed rail and the phone top bar. */
  compact?: boolean;
  side?: 'top' | 'bottom';
  align?: 'start' | 'end';
  className?: string;
}

/** Who is signed in, with workspace switch, theme, settings, refer and earn, shortcuts, Admin (admins only) and sign out. */
export function AccountMenu({ compact = false, side = 'top', align = 'start', className }: AccountMenuProps) {
  const router = useRouter();
  const me = useMe();
  const workspaces = useWorkspaces();
  const { workspace, setWorkspaceId, theme, setTheme, setShortcutsOpen } = useShell();
  const signOut = useSignOut();

  if (me.isPending) {
    return (
      <div className={cx('flex items-center gap-2.5 p-1.5', className)}>
        <Skeleton className="size-8 shrink-0 rounded-cn-full" />
        {!compact && <Skeleton className="h-8 min-w-0 flex-1" />}
      </div>
    );
  }

  if (me.isError) {
    return (
      <div role="alert" className={cx('flex items-center gap-2 p-1.5', className)}>
        {!compact && <p className="min-w-0 flex-1 text-cn-caption text-cn-fg-secondary">I couldn’t load your account.</p>}
        <IconButton label="Try loading your account again" icon={<RotateCcw />} size="sm" onClick={() => void me.refetch()} />
      </div>
    );
  }

  const user = me.data;
  const workspaceItems: MenuEntry[] = (workspaces.data ?? []).map((item) => ({
    id: `ws-${item.id}`,
    label: item.name,
    checked: item.id === workspace?.id,
    onSelect: () => setWorkspaceId(item.id),
  }));

  const items: MenuEntry[] = [
    { type: 'label', id: 'who', label: user.email },
    { type: 'separator', id: 's-ws' },
    ...(workspaceItems.length > 0 ? [{ type: 'label' as const, id: 'ws', label: 'Workspace' }, ...workspaceItems, { type: 'separator' as const, id: 's-theme' }] : []),
    { type: 'label', id: 'theme', label: 'Theme' },
    ...THEMES.map((option) => ({ id: `theme-${option.id}`, label: option.label, checked: theme === option.id, onSelect: () => setTheme(option.id) })),
    { type: 'separator', id: 's-app' },
    { id: 'settings', label: 'Settings', icon: <Settings />, onSelect: () => router.push(SETTINGS_HREF) },
    { id: 'referrals', label: 'Refer and earn', icon: <Gift />, onSelect: () => router.push(REFERRALS_HREF) },
    { id: 'shortcuts', label: 'Keyboard shortcuts', shortcut: ['?'], onSelect: () => setShortcutsOpen(true) },
    ...(user.role === 'admin' ? [{ id: 'admin', label: 'Admin', icon: <ShieldCheck />, onSelect: () => router.push(ADMIN_HREF) }] : []),
    { type: 'separator', id: 's-out' },
    { id: 'signout', label: 'Sign out', icon: <LogOut />, onSelect: () => void signOut() },
  ];

  return (
    <AvatarMenu
      name={user.name || user.email}
      detail={[`${planName(user.plan)} plan`, workspace?.name].filter(Boolean).join(' · ')}
      src={user.avatar_url ?? undefined}
      items={items}
      compact={compact}
      side={side}
      align={align}
      className={className}
    />
  );
}
