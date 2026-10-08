'use client';

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react';

import type { Workspace } from '@/lib/api/me';
import { usePersistentState } from '@/lib/design/usePersistentState';

import { THEME_STORAGE_KEY } from './theme';
import { useMe, useWorkspaces } from './useAccount';

export type ThemeChoice = 'dark' | 'light' | 'system';

interface ShellContextValue {
  theme: ThemeChoice;
  setTheme: (theme: ThemeChoice) => void;
  /** The workspace picked in the account menu; null until workspaces load. */
  workspace: Workspace | null;
  setWorkspaceId: (id: string) => void;
  commandOpen: boolean;
  setCommandOpen: (open: boolean) => void;
  shortcutsOpen: boolean;
  setShortcutsOpen: (open: boolean) => void;
  /** A page's own name for the last breadcrumb (a project's title); null uses the URL. */
  crumbLabel: string | null;
  setCrumbLabel: (label: string | null) => void;
}

const ShellContext = createContext<ShellContextValue | null>(null);

export function useShell(): ShellContextValue {
  const value = useContext(ShellContext);
  if (!value) throw new Error('useShell must be used inside <AppShell>');
  return value;
}

/** The workspace chosen in the account menu, for pages that scope by workspace. */
export const useActiveWorkspace = () => useShell().workspace;

/** Names the current page in the breadcrumb (e.g. a project's title) while the page is mounted. */
export function useBreadcrumbLabel(label: string | null | undefined) {
  const { setCrumbLabel } = useShell();
  useEffect(() => {
    setCrumbLabel(label ?? null);
    return () => setCrumbLabel(null);
  }, [label, setCrumbLabel]);
}

/** Sets `data-theme` on <html> while the shell is mounted; "system" follows the OS and its changes. */
function useApplyTheme(theme: ThemeChoice) {
  useEffect(() => {
    const root = document.documentElement;
    const query = window.matchMedia('(prefers-color-scheme: light)');
    const apply = () => {
      root.dataset.theme = theme === 'system' ? (query.matches ? 'light' : 'dark') : theme;
    };
    apply();
    query.addEventListener('change', apply);
    return () => {
      query.removeEventListener('change', apply);
      delete root.dataset.theme;
    };
  }, [theme]);
}

export function ShellProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = usePersistentState<ThemeChoice>(THEME_STORAGE_KEY, 'dark');
  // NEEDS-BACKEND: PATCH /me {active_workspace_id}; until then the choice is remembered per browser.
  const [storedWorkspaceId, setWorkspaceId] = usePersistentState<string | null>('cn_workspace', null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [crumbLabel, setCrumbLabel] = useState<string | null>(null);
  const me = useMe();
  const workspaces = useWorkspaces();
  useApplyTheme(theme);

  const workspace = useMemo(() => {
    const list = workspaces.data ?? [];
    const wanted = storedWorkspaceId ?? me.data?.active_workspace_id;
    return list.find((item) => item.id === wanted) ?? list[0] ?? null;
  }, [workspaces.data, storedWorkspaceId, me.data?.active_workspace_id]);

  const value = useMemo<ShellContextValue>(
    () => ({ theme, setTheme, workspace, setWorkspaceId, commandOpen, setCommandOpen, shortcutsOpen, setShortcutsOpen, crumbLabel, setCrumbLabel }),
    [theme, setTheme, workspace, setWorkspaceId, commandOpen, shortcutsOpen, crumbLabel],
  );

  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}
