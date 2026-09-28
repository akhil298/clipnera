"use client";
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  CalendarDays,
  Clapperboard,
  Coins,
  CornerDownLeft,
  Film,
  Folder,
  Home,
  Palette,
  Plus,
  Search,
  Settings,
  Sparkles,
} from 'lucide-react';
import type { TabType, VideoProject, ViralClip } from '@/lib/types';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { projectStatus, statusDotClass } from '@/components/ui/StatusPill';
import { SOCIAL_SETTINGS_PATH } from '@/components/social/platforms';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  projects: VideoProject[];
  onNavigate: (tab: TabType) => void;
  onOpenUpload: () => void;
  onOpenBilling: () => void;
  onOpenProject: (project: VideoProject) => void;
  onOpenClip: (clip: ViralClip, project: VideoProject) => void;
}

interface PaletteItem {
  id: string;
  group: 'Actions' | 'Pages' | 'Projects' | 'Clips';
  label: string;
  hint?: string;
  icon: React.ReactNode;
  keywords?: string;
  run: () => void;
}

const MAX_PER_GROUP = 6;

/**
 * ⌘K search over everything the dashboard already has loaded: pages,
 * actions, projects and their clips. Runs entirely on the client.
 */
export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  projects,
  onNavigate,
  onOpenUpload,
  onOpenBilling,
  onOpenProject,
  onOpenClip,
}) => {
  const router = useRouter();
  const { flags } = useFeatureFlags();
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    setQuery('');
    setActiveIndex(0);
    // Wait for the dialog to mount before focusing.
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [isOpen]);

  const allItems = useMemo<PaletteItem[]>(() => {
    const iconClass = 'w-4 h-4 text-neutral-400';
    const items: PaletteItem[] = [
      { id: 'a-new', group: 'Actions', label: 'New video', hint: 'Paste a link or upload', icon: <Plus className={iconClass} />, keywords: 'upload create youtube', run: onOpenUpload },
      { id: 'a-credits', group: 'Actions', label: 'Buy credits', hint: 'Plan & billing', icon: <Coins className={iconClass} />, keywords: 'upgrade plan pay', run: onOpenBilling },
      { id: 'p-home', group: 'Pages', label: 'Home', icon: <Home className={iconClass} />, keywords: 'dashboard', run: () => onNavigate('dashboard') },
      { id: 'p-projects', group: 'Pages', label: 'Projects', icon: <Folder className={iconClass} />, keywords: 'folders videos', run: () => onNavigate('folders') },
      ...(flags['broll_studio.reels']
        ? [{ id: 'p-reels', group: 'Pages' as const, label: 'Reels from images', icon: <Clapperboard className={iconClass} />, keywords: 'photos script', run: () => onNavigate('reels') }]
        : []),
      ...(flags.social_publishing
        ? [
            { id: 'p-scheduler', group: 'Pages' as const, label: 'Scheduler', icon: <CalendarDays className={iconClass} />, keywords: 'post publish calendar', run: () => onNavigate('scheduler') },
            { id: 'a-connect', group: 'Actions' as const, label: 'Connect a social account', hint: 'Settings', icon: <Sparkles className={iconClass} />, keywords: 'instagram tiktok youtube', run: () => router.push(SOCIAL_SETTINGS_PATH) },
          ]
        : []),
      { id: 'p-brand', group: 'Pages', label: 'Brand kit', icon: <Palette className={iconClass} />, keywords: 'logo watermark font colors captions', run: () => onNavigate('brand_kit') },
      { id: 'p-settings', group: 'Pages', label: 'Settings', icon: <Settings className={iconClass} />, keywords: 'profile team account', run: () => onNavigate('settings') },
    ];

    projects.forEach((project) => {
      const status = projectStatus(project);
      const name = project.folderName || project.title;
      items.push({
        id: `project-${project.id}`,
        group: 'Projects',
        label: name,
        hint: project.processingStatus === 'processing' ? `${Math.round(project.processingProgress || 0)}%` : `${project.clips.length} clips`,
        icon: <span className={`w-2 h-2 rounded-full ${statusDotClass(status.tone)}`} />,
        keywords: `${project.sourceChannel || ''} ${(project.tags || []).join(' ')}`,
        run: () => (project.processingStatus === 'processing' ? onNavigate('folders') : onOpenProject(project)),
      });
      project.clips.forEach((clip) => {
        items.push({
          id: `clip-${clip.id}`,
          group: 'Clips',
          label: clip.title,
          hint: `score ${clip.viralityScore}`,
          icon: <Film className={iconClass} />,
          keywords: `${clip.hook} ${name}`,
          run: () => onOpenClip(clip, project),
        });
      });
    });
    return items;
  }, [projects, flags, router, onNavigate, onOpenUpload, onOpenBilling, onOpenProject, onOpenClip]);

  const results = useMemo(() => {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    const matches = terms.length
      ? allItems.filter((item) => {
          const haystack = `${item.label} ${item.keywords || ''} ${item.group}`.toLowerCase();
          return terms.every((t) => haystack.includes(t));
        })
      : allItems.filter((item) => item.group !== 'Clips');
    const order: PaletteItem['group'][] = terms.length
      ? ['Projects', 'Clips', 'Actions', 'Pages']
      : ['Actions', 'Projects', 'Pages'];
    return order.flatMap((group) => matches.filter((m) => m.group === group).slice(0, MAX_PER_GROUP));
  }, [allItems, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`)
      ?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  if (!isOpen) return null;

  const runItem = (item: PaletteItem) => {
    onClose();
    item.run();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(results.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = results[activeIndex];
      if (item) runItem(item);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  let lastGroup = '';

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center p-3 pt-[12vh] sm:pt-[14vh] bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        className="w-full max-w-xl rounded-2xl bg-neutral-900 border border-neutral-700/80 shadow-2xl shadow-black/60 overflow-hidden"
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-3 px-4 h-14 border-b border-neutral-800">
          <Search className="w-5 h-5 text-neutral-500 shrink-0" />
          <input
            ref={inputRef}
            id="command-palette-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search projects, clips and actions"
            className="flex-1 bg-transparent text-[15px] text-white placeholder:text-neutral-500 focus:outline-none"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-palette-list"
            aria-activedescendant={results[activeIndex] ? `palette-${results[activeIndex].id}` : undefined}
            autoComplete="off"
          />
          <kbd className="hidden sm:inline font-mono text-[10.5px] px-1.5 py-0.5 rounded-md border border-neutral-700 text-neutral-400">
            esc
          </kbd>
        </div>

        <div ref={listRef} id="command-palette-list" role="listbox" className="max-h-[55vh] overflow-y-auto p-2">
          {results.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-neutral-500">No matches for “{query}”</p>
          )}
          {results.map((item, index) => {
            const showGroup = item.group !== lastGroup;
            lastGroup = item.group;
            const isActive = index === activeIndex;
            return (
              <React.Fragment key={item.id}>
                {showGroup && (
                  <div className="px-3 pt-3 pb-1.5 text-[10.5px] font-bold uppercase tracking-[0.08em] text-neutral-500">
                    {item.group}
                  </div>
                )}
                <div
                  id={`palette-${item.id}`}
                  role="option"
                  aria-selected={isActive}
                  data-index={index}
                  onMouseMove={() => setActiveIndex(index)}
                  onClick={() => runItem(item)}
                  className={`flex items-center gap-3 px-3 h-10 rounded-lg cursor-pointer text-[13.5px] ${
                    isActive ? 'bg-neutral-800 text-white' : 'text-neutral-300'
                  }`}
                >
                  <span className="w-4 flex justify-center shrink-0">{item.icon}</span>
                  <span className="flex-1 truncate font-medium">{item.label}</span>
                  {item.hint && <span className="text-xs text-neutral-500 shrink-0">{item.hint}</span>}
                  {isActive && <CornerDownLeft className="w-3.5 h-3.5 text-neutral-500 shrink-0" />}
                </div>
              </React.Fragment>
            );
          })}
        </div>

        <div className="hidden sm:flex items-center gap-4 px-4 h-10 border-t border-neutral-800 text-[11px] text-neutral-500">
          <span>↑↓ to move</span>
          <span>↵ to open</span>
          <span>⌘K to toggle</span>
        </div>
      </div>
    </div>
  );
};
