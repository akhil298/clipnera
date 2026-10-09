'use client';

import { ChevronLeft, Download, History, Keyboard, MessageSquare, MoreHorizontal } from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/Button';
import { IconButton } from '@/components/ui/IconButton';
import { Menu } from '@/components/ui/Menu';
import { Tooltip } from '@/components/ui/Tooltip';
import { TopBar } from '@/components/ui/TopBar';
import { cx, focusRing } from '@/lib/design/styles';

import { useEditor } from './context';
import { SaveState } from './SaveState';
import { VersionSwitcherZone } from './zones/VersionSwitcherZone';

/**
 * 48 px editor top bar (07 §5.4): back, project name with the version switcher over the save state;
 * Chat (768–1023), History, Shortcuts and the one amber Export ⌘E on the right. Phones keep back,
 * title, Export and a More menu. Share is hidden until a share backend exists (EB-22).
 */
export function EditorTopBar() {
  const { project, doc, layout, features, history, shortcuts, openExport } = useEditor();
  const phone = layout.arrangement === 'phone';

  const start = (
    <>
      <Link
        href="/dashboard/editor"
        aria-label="Back to editor projects"
        className={cx('inline-flex h-8 shrink-0 items-center gap-1 rounded-cn-sm px-1.5 text-cn-label font-semibold text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg', focusRing)}
      >
        <ChevronLeft aria-hidden className="size-4" />
        {!phone && <span aria-hidden>Projects</span>}
      </Link>
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <h1 className="truncate text-cn-label font-semibold text-cn-fg">{project.title}</h1>
          <VersionSwitcherZone />
        </div>
        <SaveState doc={doc} compact={phone} />
      </div>
    </>
  );

  const end = phone ? (
    <>
      <IconButton variant="primary" size="sm" label="Export" icon={<Download />} onClick={openExport} />
      <Menu
        align="end"
        trigger={(props) => <IconButton {...props} size="sm" label="More" icon={<MoreHorizontal />} />}
        items={[{ id: 'history', label: 'Version history', icon: <History />, onSelect: () => history.setOpen(true) }]}
      />
    </>
  ) : (
    <>
      {layout.arrangement === 'md' && features.conversation && (
        <Button size="sm" variant="ghost" leadingIcon={<MessageSquare />} aria-pressed={layout.conversationOpen} onClick={layout.toggleConversation}>
          Chat
        </Button>
      )}
      <IconButton size="sm" label="Version history (⌘⇧H)" icon={<History />} onClick={() => history.setOpen(true)} />
      <IconButton size="sm" label="Keyboard shortcuts (?)" icon={<Keyboard />} onClick={() => shortcuts.setOpen(true)} className="hidden lg:inline-flex" />
      <Tooltip content="Export · ⌘E">
        <Button size="sm" variant="primary" leadingIcon={<Download />} aria-keyshortcuts="Meta+E" onClick={openExport}>
          Export
        </Button>
      </Tooltip>
    </>
  );

  return <TopBar variant="editor" start={start} end={end} />;
}
