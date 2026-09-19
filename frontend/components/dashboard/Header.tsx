"use client";
import React from 'react';
import {
  Menu,
  Bell,
  Plus,
  Zap,
  Film,
  Briefcase,
  ChevronRight,
  Sparkles,
  Scissors,
  CalendarDays,
  BarChart3,
  Palette,
  Settings,
  LayoutDashboard,
  Folder,
  Crown
} from 'lucide-react';
import { useEntitlements, planLabel, isPaidPlan } from '@/hooks/useEntitlements';
import { TabType, UserProfile, Workspace, VideoProject, ViralClip } from '@/lib/types';
import { Avatar } from './Avatar';

interface HeaderProps {
  activeTab: TabType;
  onOpenMobileMenu: () => void;
  onOpenUpload: () => void;
  user: UserProfile;
  workspaces: Workspace[];
  activeProject?: VideoProject;
  selectedClip?: ViralClip;
  unreadNotificationsCount: number;
  onOpenNotifications: () => void;
  onOpenAuthModal: () => void;
  onNavigateTab: (tab: TabType) => void;
  onUpgradePlan?: () => void;
}

const TAB_TITLES: Record<TabType, { title: string; icon: React.FC<{ className?: string }> }> = {
  dashboard: { title: 'Dashboard', icon: LayoutDashboard },
  folders: { title: 'Project Folders', icon: Folder },
  generator: { title: 'AI Viral Clips', icon: Sparkles },
  editor: { title: 'Studio Editor', icon: Scissors },
  scheduler: { title: 'Social Scheduler', icon: CalendarDays },
  analytics: { title: 'Virality Analytics', icon: BarChart3 },
  brand_kit: { title: 'Brand Kit', icon: Palette },
  settings: { title: 'Settings', icon: Settings },
};

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onOpenMobileMenu,
  onOpenUpload,
  user,
  workspaces,
  activeProject,
  selectedClip,
  unreadNotificationsCount,
  onOpenNotifications,
  onOpenAuthModal,
  onNavigateTab,
  onUpgradePlan,
}) => {
  const { entitlements } = useEntitlements();
  const activeWorkspace = workspaces.find((w) => w.id === user.activeWorkspaceId) || workspaces[0];
  const CurrentIcon = TAB_TITLES[activeTab]?.icon || LayoutDashboard;

  return (
    <header className="sticky top-0 z-20 h-16 w-full shrink-0 border-b border-neutral-800/80 bg-neutral-950/90 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between gap-3">
      {/* Left: Mobile hamburger & Contextual Breadcrumb */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="lg:hidden p-2 rounded-xl bg-neutral-900 border border-neutral-800 text-neutral-300 hover:text-white transition-colors"
          title="Open Menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Current Location Breadcrumb */}
        <div className="flex items-center gap-2 text-xs min-w-0">
          <div className="hidden sm:flex items-center gap-1.5 text-neutral-400">
            <span
              onClick={() => onNavigateTab('dashboard')}
              className="hover:text-neutral-200 cursor-pointer font-medium"
            >
              Clipnera
            </span>
            <ChevronRight className="w-3 h-3 text-neutral-600" />
          </div>

          {activeTab === 'generator' && (
            <div className="hidden sm:flex items-center gap-1.5 text-neutral-400">
              <span
                onClick={() => onNavigateTab('folders')}
                className="hover:text-neutral-200 cursor-pointer font-medium flex items-center gap-1"
              >
                <Folder className="w-3.5 h-3.5 text-amber-400" />
                <span>Folders</span>
              </span>
              <ChevronRight className="w-3 h-3 text-neutral-600" />
            </div>
          )}

          <div className="flex items-center gap-1.5 font-bold text-white truncate">
            <CurrentIcon className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="truncate">{TAB_TITLES[activeTab]?.title}</span>
          </div>

          {/* If inside Studio or Clips with an active project */}
          {activeProject && (activeTab === 'generator' || activeTab === 'editor') && (
            <>
              <ChevronRight className="hidden sm:block w-3 h-3 text-neutral-600" />
              <span className="hidden sm:block text-amber-300/90 truncate max-w-[220px] text-[11px] font-mono font-semibold bg-neutral-900 px-2 py-0.5 rounded border border-neutral-800">
                📂 {activeProject.folderName || activeProject.title}
              </span>
            </>
          )}

          {activeTab === 'editor' && selectedClip && (
            <span className="hidden md:inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">
              Score: {selectedClip.viralityScore}/100
            </span>
          )}
        </div>
      </div>

      {/* Right: Quick Ingestion, Credits, Notifications, Profile */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Workspace pill on desktop */}
        <button
          onClick={onOpenAuthModal}
          className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-neutral-900 border border-neutral-800 text-xs text-neutral-300 hover:text-white hover:border-neutral-700 transition-colors"
          title="Switch Workspace"
        >
          <Briefcase className="w-3.5 h-3.5 text-amber-400" />
          <span className="max-w-[120px] truncate font-medium">{activeWorkspace?.name || 'Workspace'}</span>
        </button>

        {/* Current plan badge */}
        <button
          onClick={() => onNavigateTab('settings')}
          className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-xs font-bold transition-all ${
            isPaidPlan(entitlements)
              ? 'bg-violet-500/10 border-violet-400/30 text-violet-300 hover:border-violet-400/60'
              : 'bg-neutral-900 border-neutral-800 text-neutral-400 hover:border-neutral-700'
          }`}
          title={`You are on the ${planLabel(entitlements.plan)} plan`}
        >
          {isPaidPlan(entitlements) && <Crown className="w-3.5 h-3.5" />}
          <span>{planLabel(entitlements.plan)}</span>
        </button>

        {/* AI Credits remaining badge */}
        <button
          onClick={() => onNavigateTab('settings')}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-neutral-900 border border-neutral-800 text-xs text-neutral-300 font-mono hover:border-amber-500/40 hover:text-white transition-all"
          title={`${user.aiCreditsMinutesRemaining} of ${user.aiCreditsTotal} AI minutes remaining`}
        >
          <Zap className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
          <span className="font-semibold">
            {user.aiCreditsMinutesRemaining}
            {user.aiCreditsTotal > 0 && (
              <span className="text-neutral-500">/{user.aiCreditsTotal}</span>
            )}
            m
          </span>
        </button>

        {/* Upgrade Plan Button for Free Users */}
        {!isPaidPlan(entitlements) && (
          <button
            onClick={onUpgradePlan || (() => onNavigateTab('settings'))}
            className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all"
          >
            <Crown className="w-3.5 h-3.5" />
            <span>Upgrade Plan</span>
          </button>
        )}

        {/* Notifications Bell */}
        <button
          onClick={onOpenNotifications}
          className="relative p-2 rounded-xl bg-neutral-900 border border-neutral-800 text-neutral-300 hover:text-white hover:border-neutral-700 transition-colors"
          title="Activity Notifications"
        >
          <Bell className="w-4 h-4" />
          {unreadNotificationsCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[9px] font-bold text-neutral-950 shadow-sm">
              {unreadNotificationsCount}
            </span>
          )}
        </button>

        {/* Quick Process Video Button */}
        <button
          id="btn-header-upload"
          onClick={onOpenUpload}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all"
        >
          <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
          <span className="hidden sm:inline">New Video</span>
        </button>

        {/* User Profile Avatar */}
        <button
          onClick={onOpenAuthModal}
          className="p-0.5 rounded-xl border border-neutral-700 hover:border-amber-400 transition-colors"
          title={`Signed in as ${user.name}`}
        >
          <Avatar
            initials={user.avatarInitials}
            src={user.avatarUrl}
            alt={user.name}
            className="w-7 h-7"
          />
        </button>
      </div>
    </header>
  );
};
