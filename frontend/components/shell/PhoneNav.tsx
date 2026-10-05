'use client';

import { Menu as MenuIcon, Plus } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Drawer, MobileTabBar, type MobileTab, SidebarNavItem, SidebarSection } from '@/components/ui';

import { AccountMenu } from './AccountMenu';
import { CreditSummary } from './CreditSummary';
import { activeNavId, NEW_VIDEO_HREF, useNavItems } from './nav';
import { RecentProjects } from './RecentProjects';

const TAB_IDS = new Set(['home', 'projects', 'library']);

/**
 * Phones (< 768): Home · Projects · New · Library · More. More opens a left
 * sheet with every destination at 44 px, the credit meter and the account menu.
 */
export function PhoneNav() {
  const pathname = usePathname();
  const items = useNavItems();
  const active = activeNavId(pathname);
  const [moreOpen, setMoreOpen] = useState(false);

  useEffect(() => setMoreOpen(false), [pathname]);

  const byId = (id: string) => items.find((item) => item.id === id);
  const tabs: MobileTab[] = [
    ...['home', 'projects'].flatMap((id) => byId(id) ?? []),
    { id: 'new', label: 'New', icon: <Plus />, href: NEW_VIDEO_HREF },
    ...['library'].flatMap((id) => byId(id) ?? []),
    { id: 'more', label: 'More', icon: <MenuIcon />, onClick: () => setMoreOpen(true) },
  ];
  const activeTab = pathname.endsWith(NEW_VIDEO_HREF) ? 'new' : active && TAB_IDS.has(active) ? active : active ? 'more' : undefined;

  return (
    <>
      <MobileTabBar label="Main, phone" items={tabs} activeId={activeTab} />
      <Drawer open={moreOpen} onOpenChange={setMoreOpen} title="Menu" side="left" size="sm">
        <nav aria-label="All pages" className="flex flex-col gap-6">
          <SidebarSection className="[&_a]:h-11">
            {items.map((item) => (
              <SidebarNavItem key={item.id} label={item.label} icon={item.icon} href={item.href} active={item.id === active} />
            ))}
          </SidebarSection>
          <RecentProjects />
          <div className="flex flex-col gap-3 border-t border-cn-border pt-3">
            <CreditSummary />
            <AccountMenu side="top" />
          </div>
        </nav>
      </Drawer>
    </>
  );
}
