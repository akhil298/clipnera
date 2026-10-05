'use client';

import { Bell, Clapperboard, Coins, FolderOpen, Home, Library, LogOut, Menu as MenuIcon, Palette, Search, Settings } from 'lucide-react';
import { useState } from 'react';

import {
  AvatarMenu,
  Breadcrumbs,
  Button,
  type CommandGroup,
  CommandMenu,
  IconButton,
  Kbd,
  MobileTabBar,
  ResizablePanels,
  Sidebar,
  SidebarNavItem,
  SidebarSection,
  TopBar,
  Wordmark,
} from '@/components/ui';
import { usePersistentState } from '@/lib/design/usePersistentState';

import { GallerySection, Specimen, State } from './Specimen';

const ACCOUNT_ITEMS = [
  { type: 'label' as const, id: 'email', label: 'asha@example.com' },
  { type: 'separator' as const, id: 's1' },
  { id: 'settings', label: 'Settings', icon: <Settings />, onSelect: () => undefined },
  { id: 'shortcuts', label: 'Keyboard shortcuts', shortcut: ['?'], onSelect: () => undefined },
  { type: 'separator' as const, id: 's2' },
  { id: 'signout', label: 'Sign out', icon: <LogOut />, onSelect: () => undefined },
];

const COMMANDS: ReadonlyArray<CommandGroup> = [
  {
    id: 'go',
    label: 'Go to',
    items: [
      { id: 'projects', label: 'Projects', icon: <FolderOpen />, shortcut: ['G', 'P'] },
      { id: 'library', label: 'Library', description: 'B-roll and uploads', icon: <Library />, keywords: ['broll', 'stock'] },
      { id: 'brand', label: 'Brand kit', icon: <Palette /> },
      { id: 'billing', label: 'Plan and billing', icon: <Coins />, keywords: ['credits', 'invoice'] },
    ],
  },
  {
    id: 'recent',
    label: 'Recent projects',
    items: [
      { id: 'ep12', label: 'Episode 12 · Founders on pricing', meta: 'Ready', icon: <Clapperboard /> },
      { id: 'ep11', label: 'Episode 11 · Hiring your first PM', meta: 'Processing', icon: <Clapperboard /> },
      { id: 'old', label: 'Keynote 2025 (archived)', icon: <Clapperboard />, disabled: true },
    ],
  },
];

function SidebarPreview({ collapsed, onCollapsedChange }: { collapsed: boolean; onCollapsedChange?: (next: boolean) => void }) {
  return (
    <div className="h-96 overflow-hidden rounded-cn-lg border border-cn-border">
      <Sidebar
        label="Main"
        fullHeight={false}
        collapsed={collapsed}
        onCollapsedChange={onCollapsedChange}
        header={<Wordmark size="sm" markOnly={collapsed} />}
        footer={<AvatarMenu name="Asha Rao" detail="Pro · Rao Studio" items={ACCOUNT_ITEMS} compact={collapsed} side="top" />}
      >
        <SidebarSection>
          <SidebarNavItem href="#shell" label="Home" icon={<Home />} />
          <SidebarNavItem href="#shell" label="Projects" icon={<FolderOpen />} active />
          <SidebarNavItem href="#shell" label="Library" icon={<Library />} />
          <SidebarNavItem label="Notifications" icon={<Bell />} count={3} onClick={() => undefined} />
          <SidebarNavItem href="#shell" label="Brand kit" icon={<Palette />} disabled />
        </SidebarSection>
        <SidebarSection title="Recent">
          <SidebarNavItem href="#shell" label="Episode 12 · Founders on pricing" icon={<Clapperboard />} />
          <SidebarNavItem href="#shell" label="Episode 11" icon={<Clapperboard />} trailing={<span className="font-cn-mono text-cn-caption text-cn-accent-text">42%</span>} />
        </SidebarSection>
      </Sidebar>
    </div>
  );
}

function PanelBody({ title }: { title: string }) {
  return (
    <div className="flex h-full items-center justify-center bg-cn-surface p-3 text-center text-cn-label text-cn-fg-secondary">{title}</div>
  );
}

export function ShellSection() {
  const [collapsed, setCollapsed] = usePersistentState('cn-gallery:sidebar', false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [picked, setPicked] = useState<string>();

  return (
    <GallerySection id="shell" title="App shell" intro="Building blocks for the signed-in frame: sidebar and rail, top bar, breadcrumbs, phone tab bar, resizable panes and the ⌘K menu.">
      <Specimen title="Sidebar, SidebarSection, SidebarNavItem, AvatarMenu" note="The toggle persists in this browser (usePersistentState). Rail items keep their names as tooltips; counts become a dot.">
        <div className="flex flex-wrap gap-6">
          <State label={collapsed ? 'rail (toggle to expand)' : 'expanded (toggle to collapse)'}>
            <SidebarPreview collapsed={collapsed} onCollapsedChange={setCollapsed} />
          </State>
          <State label="rail">
            <SidebarPreview collapsed />
          </State>
        </div>
      </Specimen>

      <Specimen title="TopBar and Breadcrumbs" note="Breadcrumbs collapse to a back link on phones. The prompt entry opens the CommandMenu.">
        <div className="overflow-hidden rounded-cn-lg border border-cn-border">
          <TopBar
            sticky={false}
            start={
              <>
                <IconButton label="Open navigation" icon={<MenuIcon />} size="sm" className="md:hidden" />
                <Breadcrumbs items={[{ label: 'Projects', href: '#shell' }, { label: 'Episode 12 · Founders on pricing', href: '#shell' }, { label: 'Clips' }]} />
              </>
            }
            end={
              <>
                <Button variant="secondary" size="sm" leadingIcon={<Search />} onClick={() => setCommandOpen(true)} className="hidden sm:inline-flex">
                  Ask or go <Kbd keys={['⌘', 'K']} />
                </Button>
                <IconButton label="Ask Clipnera or go to a page" icon={<Search />} size="sm" className="sm:hidden" onClick={() => setCommandOpen(true)} />
                <AvatarMenu name="Asha Rao" items={ACCOUNT_ITEMS} compact align="end" />
              </>
            }
          />
        </div>
      </Specimen>

      <Specimen title="CommandMenu" note={`Modal combobox: focus stays in the field; ↑↓ move, Enter chooses, Escape closes. Grouped, filtered, with disabled rows. ${picked ? `Last chosen: ${picked}.` : ''}`}>
        <Button variant="secondary" leadingIcon={<Search />} onClick={() => setCommandOpen(true)}>
          Open command menu
        </Button>
        <CommandMenu open={commandOpen} onOpenChange={setCommandOpen} groups={COMMANDS} onSelect={(item) => setPicked(item.label)} />
      </Specimen>

      <Specimen title="MobileTabBar" note="Fixed at the bottom below md in real screens; shown inline here.">
        <div className="mx-auto max-w-sm overflow-hidden rounded-cn-lg border border-cn-border">
          <MobileTabBar
            label="Main"
            placement="inline"
            activeId="projects"
            items={[
              { id: 'home', label: 'Home', icon: <Home />, href: '#shell' },
              { id: 'projects', label: 'Projects', icon: <FolderOpen />, href: '#shell' },
              { id: 'library', label: 'Library', icon: <Library />, href: '#shell' },
              { id: 'inbox', label: 'Inbox', icon: <Bell />, count: 2, onClick: () => undefined },
            ]}
          />
        </div>
      </Specimen>

      <Specimen title="ResizablePanels" note="Drag a handle, or focus it and use ←/→ (Shift for 10%), Home/End; Enter or double-click resets. Sizes persist.">
        <ResizablePanels
          storageKey="gallery-editor"
          className="h-56 overflow-hidden rounded-cn-lg border border-cn-border"
          panels={[
            { id: 'chat', label: 'Conversation', defaultSize: 30, minSize: 20, maxSize: 50, children: <PanelBody title="Conversation" /> },
            { id: 'preview', label: 'Preview', defaultSize: 45, minSize: 30, children: <PanelBody title="Preview" /> },
            { id: 'tools', label: 'Tools', defaultSize: 25, minSize: 15, maxSize: 40, children: <PanelBody title="Tools" /> },
          ]}
        />
      </Specimen>
    </GallerySection>
  );
}
