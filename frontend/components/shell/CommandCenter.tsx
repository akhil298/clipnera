'use client';

import { BarChart3, Building2, CreditCard, FolderOpen, Keyboard, LogOut, Moon, Plus, Settings, ShieldCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { type CommandGroup, CommandMenu, filterCommandGroups } from '@/components/ui';
import { useFlag } from '@/lib/flags/useFlag';

import { ADMIN_HREF, BILLING_HREF, NEW_VIDEO_HREF, SETTINGS_HREF, useNavItems } from './nav';
import { projectHref } from './RecentProjects';
import { type ThemeChoice, useShell } from './ShellContext';
import { isRunning, useMe, useRecentProjects, useWorkspaces } from './useAccount';
import { useSignOut } from './useSignOut';

/** Projects listed before anything is typed. */
const RECENT_SHOWN = 5;
const THEME_LABEL: Record<ThemeChoice, string> = { dark: 'Dark', light: 'Light', system: 'Match system' };

/** "/go epis" and "epis" search the same things: `/go` is the spoken way in from the prompt (D5). */
const searchText = (text: string) => text.replace(/^\/go\b\s*/i, '');

/**
 * ⌘K "Go to": pages, projects (with live status), workspace switch, theme,
 * shortcuts and sign out: everything the old CommandPalette reached, plus what it lacked.
 */
export function CommandCenter() {
  const router = useRouter();
  const { commandOpen, setCommandOpen, setShortcutsOpen, setTheme, theme, workspace, setWorkspaceId } = useShell();
  const navItems = useNavItems();
  const publishing = useFlag('social_publishing');
  const me = useMe();
  const workspaces = useWorkspaces();
  const projects = useRecentProjects();
  const signOut = useSignOut();
  const [text, setText] = useState('');
  const query = searchText(text);
  const go = (href: string) => () => router.push(href);

  const groups: CommandGroup[] = [
    {
      id: 'pages',
      label: 'Pages',
      items: [
        ...navItems.map((item) => ({ id: `page-${item.id}`, label: item.label, icon: item.icon, onSelect: go(item.href) })),
        { id: 'page-new', label: 'New video', description: 'Upload a file or paste a link', icon: <Plus />, keywords: ['upload', 'youtube', 'link'], onSelect: go(NEW_VIDEO_HREF) },
        ...(publishing ? [{ id: 'page-analytics', label: 'Analytics', icon: <BarChart3 />, keywords: ['stats', 'views'], onSelect: go('/dashboard/analytics') }] : []),
        { id: 'page-settings', label: 'Settings', icon: <Settings />, keywords: ['account', 'profile', 'team'], onSelect: go(SETTINGS_HREF) },
        { id: 'page-billing', label: 'Plan and credits', icon: <CreditCard />, keywords: ['billing', 'upgrade', 'pro', 'payment'], onSelect: go(BILLING_HREF) },
        ...(me.data?.role === 'admin' ? [{ id: 'page-admin', label: 'Admin', icon: <ShieldCheck />, onSelect: go(ADMIN_HREF) }] : []),
      ],
    },
    {
      id: 'projects',
      label: query ? 'Projects' : 'Recent projects',
      items: (query ? projects.data ?? [] : (projects.data ?? []).slice(0, RECENT_SHOWN)).map((project) => ({
        id: `project-${project.id}`,
        label: project.title,
        description: isRunning(project.status) ? 'Making clips' : project.status === 'failed' ? 'Failed' : `${project.clips.length} clips`,
        icon: <FolderOpen />,
        onSelect: go(projectHref(project.id)),
      })),
    },
    {
      id: 'account',
      label: 'Account',
      items: [
        ...(workspaces.data && workspaces.data.length > 1
          ? workspaces.data
              .filter((item) => item.id !== workspace?.id)
              .map((item) => ({ id: `ws-${item.id}`, label: `Switch to ${item.name}`, icon: <Building2 />, keywords: ['workspace'], onSelect: () => setWorkspaceId(item.id) }))
          : []),
        ...(Object.keys(THEME_LABEL) as ThemeChoice[])
          .filter((choice) => choice !== theme)
          .map((choice) => ({ id: `theme-${choice}`, label: `Theme: ${THEME_LABEL[choice]}`, icon: <Moon />, keywords: ['appearance', 'dark', 'light'], onSelect: () => setTheme(choice) })),
        { id: 'shortcuts', label: 'Keyboard shortcuts', icon: <Keyboard />, shortcut: ['?'], onSelect: () => setShortcutsOpen(true) },
        { id: 'signout', label: 'Sign out', icon: <LogOut />, keywords: ['log out'], onSelect: () => void signOut() },
      ],
    },
  ];

  return (
    <CommandMenu
      open={commandOpen}
      onOpenChange={(open) => {
        setCommandOpen(open);
        if (!open) setText('');
      }}
      label="Go to"
      placeholder="Go to a page, project or setting"
      query={text}
      onQueryChange={setText}
      filter={false}
      groups={filterCommandGroups(groups, query)}
      onSelect={() => undefined}
      loading={projects.isPending && query.length > 0}
      emptyText={projects.isError ? 'Nothing matches. I couldn’t load your projects, so they aren’t listed.' : 'Nothing matches'}
    />
  );
}
