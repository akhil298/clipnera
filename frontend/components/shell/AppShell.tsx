'use client';

import { Search } from 'lucide-react';
import type { ReactNode } from 'react';

import { IconButton, ToastProvider, TopBar } from '@/components/ui';
import { HeaderActions } from '@/components/shell/header-actions';

import { AccountMenu } from './AccountMenu';
import { AppSidebar } from './AppSidebar';
import { CommandCenter } from './CommandCenter';
import { OfflineBanner } from './OfflineBanner';
import { PhoneNav } from './PhoneNav';
import { ShellBreadcrumbs } from './ShellBreadcrumbs';
import { ShellProvider, useShell } from './ShellContext';
import { ShortcutsDialog } from './ShortcutsDialog';
import { useShellShortcuts } from './useShellShortcuts';

function ShellTopBar() {
  const { setCommandOpen } = useShell();
  return (
    <TopBar
      start={<ShellBreadcrumbs />}
      end={
        <>
          <IconButton
            label="Go to anything (⌘K)"
            icon={<Search />}
            size="sm"
            aria-keyshortcuts="Meta+K Control+K"
            onClick={() => setCommandOpen(true)}
          />
          <HeaderActions />
          <AccountMenu compact side="bottom" align="end" className="md:hidden" />
        </>
      }
    />
  );
}

function ShellFrame({ children, modal }: { children: ReactNode; modal: ReactNode }) {
  useShellShortcuts();
  return (
    <div className="flex min-h-dvh bg-cn-bg font-cn-sans text-cn-fg">
      <a
        href="#main"
        className="fixed left-4 top-2 z-cn-skiplink -translate-y-16 rounded-cn-md bg-cn-accent px-3 py-2 text-cn-label font-semibold text-cn-accent-fg focus:translate-y-0"
      >
        Skip to content
      </a>
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <ShellTopBar />
        <OfflineBanner />
        <main id="main" tabIndex={-1} className="flex min-w-0 flex-1 flex-col pb-16 focus-visible:outline-none md:pb-0">
          <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-4 py-6 sm:px-6 lg:px-8">{children}</div>
        </main>
      </div>
      <PhoneNav />
      <CommandCenter />
      <ShortcutsDialog />
      {modal}
    </div>
  );
}

/**
 * The signed-in frame for every /dashboard page, mounted once by the layout so
 * it never remounts between pages: sidebar (rail on tablets), top bar with the
 * breadcrumb and HeaderActions, phone tab bar with More, ⌘K Go to, and the
 * @modal slot. Pages own their content; the shell owns the 1280 max width and
 * the 16 / 24 / 32 gutters.
 */
export function AppShell({ children, modal }: { children: ReactNode; modal: ReactNode }) {
  return (
    <ToastProvider>
      <ShellProvider>
        <ShellFrame modal={modal}>{children}</ShellFrame>
      </ShellProvider>
    </ToastProvider>
  );
}
