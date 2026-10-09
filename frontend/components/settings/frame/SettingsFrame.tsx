'use client';

import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

import { useBreadcrumbLabel } from '@/components/shell';
import { cx } from '@/lib/design/styles';

import { sectionForPath } from './sections';
import { SettingsNav } from './SettingsNav';
import { useSettingsSections } from './useSettingsSections';

/**
 * The settings frame (screens/03 §9.1, 07 §5.6).
 * Desktop (≥ 1024): "Settings" heading, a 224 px sticky nav with search, and a 672 px content column.
 * Below that: `/dashboard/settings` is the list of sections, and each section is its own page
 * titled by the section; the top bar's back link returns to the list.
 */
export function SettingsFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const sections = useSettingsSections();
  const current = sectionForPath(pathname);
  useBreadcrumbLabel(current?.label);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-cn-fast sm:px-6 lg:px-8 lg:py-8">
      <header className="space-y-1">
        <h1 className="text-cn-title font-semibold text-cn-fg lg:text-cn-title-lg">
          {current ? (
            <>
              <span className="lg:hidden">{current.label}</span>
              <span className="hidden lg:inline">Settings</span>
            </>
          ) : (
            'Settings'
          )}
        </h1>
        <p className={cx('text-cn-body text-cn-fg-secondary', current && 'hidden lg:block')}>
          Your account, workspace, plan and the accounts you publish to.
        </p>
      </header>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-10">
        <div className={cx('lg:sticky lg:top-6 lg:block lg:w-56 lg:shrink-0', current && 'hidden')}>
          <div className="lg:hidden">
            <SettingsNav sections={sections} currentId={null} variant="list" />
          </div>
          <div className="hidden lg:block">
            <SettingsNav sections={sections} currentId={current?.id ?? null} variant="rail" />
          </div>
        </div>
        <div className={cx('min-w-0 max-w-2xl flex-1 space-y-6', !current && 'hidden lg:block')}>{children}</div>
      </div>
    </div>
  );
}
