'use client';

import { FolderOpen, Link2, Palette, Upload } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useId, useRef, useState } from 'react';

import { type CommandGroup, CommandList, commandOptionId, SearchField, useCommandList } from '@/components/ui';

const LINK = /^https?:\/\/\S+$/i;
const VIDEO_ACCEPT = 'video/*';

export interface AttachMenuProps {
  close: () => void;
  /** Files picked from the device. Leave out to hide "Upload video" (no upload path yet). */
  onAddFiles?: (files: File[]) => void;
  /** Puts a pasted link into the prompt. */
  onInsertText: (text: string) => void;
}

/** The composer's + popover (07 §6.1): search, then Upload video · Paste link · From library · Brand kit. */
export function AttachMenu({ close, onAddFiles, onInsertText }: AttachMenuProps) {
  const router = useRouter();
  const id = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');

  const pasteLink = async () => {
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (LINK.test(text)) onInsertText(text);
    } catch {
      // Clipboard access refused: the person pastes into the box instead.
    }
    close();
  };

  const go = (href: string) => {
    close();
    router.push(href);
  };

  const groups: CommandGroup[] = [
    {
      id: 'add',
      items: [
        ...(onAddFiles
          ? [{ id: 'upload', label: 'Upload video', description: 'MP4, MOV, WebM or MKV', icon: <Upload />, keywords: ['file', 'computer'], onSelect: () => fileRef.current?.click() }]
          : []),
        { id: 'paste', label: 'Paste link', description: 'From your clipboard', icon: <Link2 />, keywords: ['url', 'youtube'], onSelect: () => void pasteLink() },
        { id: 'library', label: 'From library', description: 'Footage and B-roll you can use', icon: <FolderOpen />, onSelect: () => go('/dashboard/library') },
        { id: 'brand', label: 'Brand kit', description: 'Colours, logo and caption style', icon: <Palette />, onSelect: () => go('/dashboard/brand-kit') },
      ],
    },
  ];
  const list = useCommandList(groups, query, () => undefined);
  const listId = `${id}-attach`;

  return (
    <div className="flex w-72 max-w-full flex-col gap-1">
      <SearchField
        value={query}
        onValueChange={setQuery}
        size="sm"
        placeholder="Search"
        aria-label="Search what to add"
        role="combobox"
        aria-expanded
        aria-controls={listId}
        aria-activedescendant={list.activeId ? commandOptionId(listId, list.activeId) : undefined}
        onKeyDown={list.onKeyDown}
        autoFocus
      />
      <CommandList id={listId} label="Add to the prompt" groups={list.groups} activeId={list.activeId} onActiveChange={list.setActiveId} onChoose={list.select} query={query} />
      {onAddFiles && (
        <input
          ref={fileRef}
          type="file"
          accept={VIDEO_ACCEPT}
          hidden
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            if (files.length > 0) onAddFiles(files);
            close();
          }}
        />
      )}
    </div>
  );
}
