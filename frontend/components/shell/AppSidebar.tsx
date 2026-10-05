'use client';

import { Plus } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { buttonClasses, Sidebar, SidebarNavItem, SidebarSection, useSidebarCollapsed, Wordmark } from '@/components/ui';
import { useDismissOnOutsidePointer } from '@/lib/design/layers';
import { cx, focusRing } from '@/lib/design/styles';
import { usePersistentState } from '@/lib/design/usePersistentState';

import { AccountMenu } from './AccountMenu';
import { CreditSummary } from './CreditSummary';
import { activeNavId, HOME_HREF, NEW_VIDEO_HREF, useNavItems } from './nav';
import { RecentProjects } from './RecentProjects';
import { useMediaQuery } from './useMediaQuery';

/** "New video": an action, not a destination. Secondary, so the page keeps the one amber action. */
function NewVideo() {
  const collapsed = useSidebarCollapsed();
  if (collapsed) {
    return (
      <ul>
        <SidebarNavItem label="New video" icon={<Plus />} href={NEW_VIDEO_HREF} />
      </ul>
    );
  }
  return (
    <Link href={NEW_VIDEO_HREF} className={cx(buttonClasses({ variant: 'secondary', size: 'md' }), 'w-full')}>
      <Plus aria-hidden className="size-4" />
      New video
    </Link>
  );
}

function Brand() {
  const collapsed = useSidebarCollapsed();
  return (
    <Link href={HOME_HREF} aria-label="Clipnera home" className={cx('rounded-cn-sm', focusRing)}>
      <Wordmark size="sm" markOnly={collapsed} />
    </Link>
  );
}

function Footer() {
  const collapsed = useSidebarCollapsed();
  return (
    <>
      <CreditSummary />
      <AccountMenu compact={collapsed} side="top" align="start" />
    </>
  );
}

/**
 * Desktop (≥ 1024): 240 px, collapsible to the rail, remembered per browser.
 * Tablet (768–1023): always the rail; its expand button opens the full
 * sidebar over the page (Escape, an outside click or navigating closes it).
 * Phones get the tab bar instead.
 */
export function AppSidebar() {
  const pathname = usePathname();
  const items = useNavItems();
  const active = activeNavId(pathname);
  const desktop = useMediaQuery('(min-width: 1024px)', true);
  const [savedCollapsed, setSavedCollapsed] = usePersistentState('cn_sidebar_collapsed', false);
  const [tabletOpen, setTabletOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const overlay = !desktop && tabletOpen;

  useEffect(() => setTabletOpen(false), [pathname, desktop]);
  useDismissOnOutsidePointer(overlay, [wrapperRef], () => setTabletOpen(false));
  useEffect(() => {
    if (!overlay) return;
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setTabletOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [overlay]);

  return (
    <div ref={wrapperRef} className={cx('sticky top-0 hidden h-dvh shrink-0 md:block', overlay ? 'z-cn-drawer w-16' : 'z-cn-sticky')}>
      <Sidebar
        label="Main"
        fullHeight={false}
        collapsed={desktop ? savedCollapsed : !tabletOpen}
        onCollapsedChange={(next) => (desktop ? setSavedCollapsed(next) : setTabletOpen(!next))}
        header={<Brand />}
        footer={<Footer />}
        className={cx(overlay && 'absolute inset-y-0 left-0 shadow-cn-3')}
      >
        <NewVideo />
        <SidebarSection>
          {items.map((item) => (
            <SidebarNavItem key={item.id} label={item.label} icon={item.icon} href={item.href} active={item.id === active} />
          ))}
        </SidebarSection>
        <RecentProjects />
      </Sidebar>
    </div>
  );
}
