"use client";
import React from 'react';
import { CalendarDays, Clapperboard, Folder, Home, Menu, Palette, Plus } from 'lucide-react';
import type { TabType } from '@/lib/types';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';

interface MobileTabBarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  onOpenUpload: () => void;
  /** Opens the full menu (every other page, workspace, credits, admin). */
  onOpenMore: () => void;
}

/**
 * Phone navigation: the four most used places plus a centre Create button.
 * Everything else stays one tap away under More.
 */
export const MobileTabBar: React.FC<MobileTabBarProps> = ({ activeTab, onTabChange, onOpenUpload, onOpenMore }) => {
  const { flags } = useFeatureFlags();

  // The fourth slot is the scheduler when publishing is on, otherwise the
  // next most used page, so the bar never shows a dead end.
  const fourth: { id: TabType; label: string; icon: React.FC<{ className?: string }> } = flags.social_publishing
    ? { id: 'scheduler', label: 'Schedule', icon: CalendarDays }
    : flags['broll_studio.reels']
      ? { id: 'reels', label: 'Reels', icon: Clapperboard }
      : { id: 'brand_kit', label: 'Brand', icon: Palette };

  const tabs = [
    { id: 'dashboard' as TabType, label: 'Home', icon: Home, match: ['dashboard'] },
    { id: 'folders' as TabType, label: 'Projects', icon: Folder, match: ['folders', 'generator', 'editor'] },
    { ...fourth, match: [fourth.id] },
  ];
  const coveredTabs = tabs.flatMap((t) => t.match);
  const moreActive = !coveredTabs.includes(activeTab);

  const tabButton = (tab: (typeof tabs)[number]) => {
    const Icon = tab.icon;
    const isActive = tab.match.includes(activeTab);
    return (
      <button
        key={tab.id}
        type="button"
        onClick={() => onTabChange(tab.id)}
        aria-current={isActive ? 'page' : undefined}
        className={`flex-1 flex flex-col items-center gap-1 pt-2 text-[10.5px] font-semibold transition-colors ${
          isActive ? 'text-amber-400' : 'text-neutral-500 active:text-neutral-300'
        }`}
      >
        <Icon className="w-5 h-5" />
        {tab.label}
      </button>
    );
  };

  return (
    <nav
      aria-label="Main"
      className="md:hidden fixed bottom-0 inset-x-0 z-40 flex items-start bg-neutral-950/95 backdrop-blur-md border-t border-neutral-800 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] h-[calc(4rem+env(safe-area-inset-bottom))]"
    >
      {tabButton(tabs[0])}
      {tabButton(tabs[1])}
      <div className="flex-1 flex justify-center">
        <button
          type="button"
          onClick={onOpenUpload}
          className="-mt-5 w-14 h-14 rounded-2xl bg-amber-500 active:bg-amber-400 text-neutral-950 flex items-center justify-center shadow-lg shadow-amber-500/30 border-4 border-neutral-950"
          aria-label="New video"
        >
          <Plus className="w-6 h-6 stroke-[2.5]" />
        </button>
      </div>
      {tabButton(tabs[2])}
      <button
        type="button"
        onClick={onOpenMore}
        aria-current={moreActive ? 'page' : undefined}
        className={`flex-1 flex flex-col items-center gap-1 pt-2 text-[10.5px] font-semibold transition-colors ${
          moreActive ? 'text-amber-400' : 'text-neutral-500 active:text-neutral-300'
        }`}
      >
        <Menu className="w-5 h-5" />
        More
      </button>
    </nav>
  );
};
