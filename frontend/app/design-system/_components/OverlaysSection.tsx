'use client';

import { Bookmark, ChevronDown, Copy, Ellipsis, History, Pencil, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Drawer } from '@/components/ui/Drawer';
import { IconButton } from '@/components/ui/IconButton';
import { Input } from '@/components/ui/Input';
import { Menu, type MenuEntry } from '@/components/ui/Menu';
import { Popover } from '@/components/ui/Popover';
import { Switch } from '@/components/ui/Switch';
import { type ToastOptions, useToast } from '@/components/ui/Toast';
import { Tooltip } from '@/components/ui/Tooltip';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

const TOASTS: ReadonlyArray<{ label: string; toast: ToastOptions }> = [
  { label: 'Success', toast: { tone: 'success', title: 'Export ready', description: 'Opening hook · 0:42 · 1080p', action: { label: 'Download', onClick: () => {} } } },
  { label: 'Info', toast: { tone: 'info', title: 'Reconnecting', description: 'Your edit is still running.' } },
  {
    label: 'Error (stays)',
    toast: {
      tone: 'danger',
      title: 'Export did not finish',
      description: 'Your project and its versions are safe.',
      action: { label: 'Try again', onClick: () => {} },
    },
  },
  { label: 'Neutral', toast: { title: 'Copied link' } },
];

export function OverlaysSection() {
  const toast = useToast();
  const [dialog, setDialog] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [drawer, setDrawer] = useState<'right' | 'bottom' | null>(null);
  const [captions, setCaptions] = useState(true);

  const menuItems: ReadonlyArray<MenuEntry> = [
    { id: 'rename', label: 'Rename', icon: <Pencil />, shortcut: ['⌘', 'R'], onSelect: () => toast.show({ title: 'Rename chosen' }) },
    { id: 'duplicate', label: 'Duplicate', icon: <Copy />, onSelect: () => toast.show({ title: 'Duplicate chosen' }) },
    { id: 'bookmark', label: 'Bookmark version', icon: <Bookmark />, disabled: true, onSelect: () => {} },
    { type: 'separator', id: 'sep-1' },
    { type: 'label', id: 'label-show', label: 'Show' },
    { id: 'captions', label: 'Captions', checked: captions, onSelect: () => setCaptions(!captions) },
    { type: 'separator', id: 'sep-2' },
    { id: 'delete', label: 'Delete clip', icon: <Trash2 />, danger: true, onSelect: () => setConfirm(true) },
  ];

  const runDelete = () => {
    setDeleting(true);
    setTimeout(() => {
      setDeleting(false);
      setConfirm(false);
      toast.show({ tone: 'success', title: 'Clip deleted', action: { label: 'Undo', onClick: () => {} } });
    }, 1200);
  };

  return (
    <GallerySection
      id="overlays"
      title="Overlays"
      intro="Each opens in a portal on <body> at its own layer. Try the keyboard: Escape closes the newest layer only, focus returns to the trigger."
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="Tooltip" note="Hover (500 ms delay) or focus (instant). Escape hides it. Never the only place information lives.">
          <StateGrid className="sm:grid-cols-2 lg:grid-cols-2">
            <State label="on a button">
              <Tooltip content="Generates up to 10 clips">
                <Button variant="secondary">Find moments</Button>
              </Tooltip>
            </State>
            <State label="on an icon button">
              <IconButton label="Version history" icon={<History />} />
            </State>
          </StateGrid>
        </Specimen>

        <Specimen title="Menu" note="Arrows, Home/End, type a letter, Enter. Disabled items are skipped. Destructive last, after a separator.">
          <Menu
            items={menuItems}
            trigger={(props) => (
              <Button {...props} variant="secondary" trailingIcon={<ChevronDown />}>
                Clip actions
              </Button>
            )}
          />
          <span className="ml-3 inline-block">
            <Menu
              align="end"
              items={menuItems}
              trigger={({ ref, ...props }) => <IconButton ref={ref} {...props} label="More actions" icon={<Ellipsis />} />}
            />
          </span>
        </Specimen>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="Popover" note="Non-modal. Focus moves in; Escape, outside click or tabbing away closes it.">
          <Popover
            title="Credits"
            trigger={(props) => (
              <Button {...props} variant="secondary">
                1,240 credits
              </Button>
            )}
          >
            {(close) => (
              <div className="space-y-3 text-cn-label text-cn-fg-secondary">
                <p>Monthly plan: 1,000 · Packs: 240. Packs never expire.</p>
                <Button size="sm" fullWidth onClick={close}>
                  Add credits
                </Button>
              </div>
            )}
          </Popover>
        </Specimen>

        <Specimen title="Toast" note="Errors stay until dismissed. Others leave after 6 s, paused on hover, focus or a hidden tab. Read once by screen readers.">
          <div className="flex flex-wrap gap-2">
            {TOASTS.map(({ label, toast: options }) => (
              <Button key={label} size="sm" variant="secondary" onClick={() => toast.show(options)}>
                {label}
              </Button>
            ))}
          </div>
        </Specimen>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Specimen title="Dialog" note="Centred from 640px, a bottom sheet on phones. Focus trapped; returns to the trigger.">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setDialog(true)}>
              Rename project
            </Button>
            <Button variant="danger" onClick={() => setConfirm(true)}>
              Delete clip
            </Button>
          </div>
        </Specimen>
        <Specimen title="Drawer" note="Side panel or phone sheet. Same focus rules as Dialog; sits one layer below it.">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setDrawer('right')}>
              Version history
            </Button>
            <Button variant="secondary" onClick={() => setDrawer('bottom')}>
              Bottom sheet
            </Button>
          </div>
        </Specimen>
      </div>

      <Dialog
        open={dialog}
        onOpenChange={setDialog}
        title="Rename project"
        description="Shown on the project card and in exports."
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(false)}>
              Cancel
            </Button>
            <Button onClick={() => setDialog(false)}>Save</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input label="Name" defaultValue="Founder podcast, episode 12" data-autofocus />
          <Menu
            items={menuItems}
            trigger={(props) => (
              <Button {...props} size="sm" variant="ghost" trailingIcon={<ChevronDown />}>
                A menu inside a dialog
              </Button>
            )}
          />
        </div>
      </Dialog>

      <Dialog
        open={confirm}
        onOpenChange={(open) => !deleting && setConfirm(open)}
        role="alertdialog"
        size="sm"
        dismissible={!deleting}
        title="Delete this clip?"
        description="The clip and its versions are removed. Clips already posted stay posted."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(false)} disabled={deleting} data-autofocus>
              Keep clip
            </Button>
            <Button variant="danger" loading={deleting} loadingLabel="Deleting" onClick={runDelete}>
              Delete clip
            </Button>
          </>
        }
      />

      <Drawer
        open={drawer !== null}
        onOpenChange={(open) => !open && setDrawer(null)}
        side={drawer ?? 'right'}
        title={drawer === 'bottom' ? 'Prompt' : 'Version history'}
        description={drawer === 'bottom' ? 'On phones the prompt bar opens as a sheet over the preview.' : '12 versions. Restoring one makes it the newest; nothing is deleted.'}
      >
        <div className="space-y-4 text-cn-body text-cn-fg-secondary">
          <Switch label="Show only bookmarked versions" />
          <p>Version list goes here (spec: 02-design-system.md, VersionHistory item).</p>
        </div>
      </Drawer>
    </GallerySection>
  );
}
