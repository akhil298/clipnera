"use client";
import React, { useState } from 'react';
import {
  Sparkles,
  Scissors,
  Film,
  BarChart3,
  CalendarDays,
  Plus,
  Zap,
  Palette,
  Settings,
  LayoutDashboard,
  Briefcase,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Folder,
  FolderOpen,
  FolderPlus,
  X
} from 'lucide-react';
import { TabType, UserProfile, Workspace, VideoProject, ViralClip } from '@/lib/types';
import { Skeleton } from '@/components/skeletons';
import { useEntitlements, planLabel, isPaidPlan, daysUntilRenewal } from '@/hooks/useEntitlements';

interface SidebarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  onOpenUpload: () => void;
  user: UserProfile;
  workspaces: Workspace[];
  projects?: VideoProject[];
  activeProject?: VideoProject;
  onSelectProject?: (project: VideoProject) => void;
  selectedClip?: ViralClip;
  onOpenAuthModal: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  onOpenUpload,
  user,
  workspaces,
  projects = [],
  activeProject,
  onSelectProject,
  selectedClip,
  onOpenAuthModal,
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
}) => {
  const [foldersExpanded, setFoldersExpanded] = useState(true);
  const { entitlements } = useEntitlements();
  const renewalDays = daysUntilRenewal(entitlements.current_period_end);
  const activeWorkspace = workspaces.find((w) => w.id === user.activeWorkspaceId) || workspaces[0];

  const primaryNavItems = [
    {
      id: 'dashboard' as TabType,
      label: 'Dashboard',
      icon: LayoutDashboard,
      description: 'Overview & recent projects',
    },
    {
      id: 'folders' as TabType,
      label: 'Project Folders',
      icon: Folder,
      badge: projects.length ? `${projects.length}` : undefined,
      description: 'Organized video folders & YouTube ingests',
    },
    {
      id: 'generator' as TabType,
      label: 'AI Viral Clips',
      icon: Sparkles,
      badge: activeProject?.clips?.length ? `${activeProject.clips.length}` : undefined,
      description: 'Extracted viral short clips',
    },
    {
      id: 'editor' as TabType,
      label: 'Studio Editor',
      icon: Scissors,
      badge: selectedClip ? 'Active' : undefined,
      description: 'Captions, B-roll & facial tracking',
    },
  ];

  const distributionNavItems: Array<{ id: TabType; label: string; icon: React.FC<{ className?: string }>; description: string }> = [
    // {
    //   id: 'scheduler' as TabType,
    //   label: 'Social Scheduler',
    //   icon: CalendarDays,
    //   description: 'TikTok, IG & Shorts auto-post',
    // },
    // {
    //   id: 'analytics' as TabType,
    //   label: 'Virality Analytics',
    //   icon: BarChart3,
    //   description: 'Retention curves & virality scores',
    // },
  ];

  const settingsNavItems = [
    {
      id: 'brand_kit' as TabType,
      label: 'Brand Kit',
      icon: Palette,
      description: 'Fonts, colors & watermark styles',
    },
    {
      id: 'settings' as TabType,
      label: 'Settings & Billing',
      icon: Settings,
      description: 'Workspace, keys & subscriptions',
    },
  ];

  const handleNavClick = (tab: TabType) => {
    onTabChange(tab);
    onCloseMobile();
  };

  const aiCreditPercent = Math.min(
    100,
    Math.max(0, Math.round((user.aiCreditsMinutesRemaining / user.aiCreditsTotal) * 100))
  );

  const sidebarContent = (
    <div className="h-full flex flex-col justify-between bg-neutral-950 text-neutral-200 select-none">
      {/* Top section: Brand & Workspace */}
      <div className="p-4 space-y-4">
        {/* Brand Header */}
        <div className="flex items-center justify-between">
          <div
            onClick={() => handleNavClick('dashboard')}
            className="cursor-pointer flex items-center gap-2.5 group"
          >
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-amber-500 text-neutral-950 shadow-md shadow-amber-500/20 group-hover:scale-105 transition-all shrink-0">
              <Film className="w-5 h-5 stroke-[2.2]" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="font-extrabold text-base tracking-tight text-white font-['Plus_Jakarta_Sans',sans-serif]">
                    Clip<span className="text-amber-400">nera</span>
                  </span>
                  <span className="px-1.5 py-0.2 text-[9px] font-bold rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 uppercase">
                    PRO
                  </span>
                </div>
                <span className="text-[10px] text-neutral-400">AI Video Repurposing</span>
              </div>
            )}
          </div>

          {/* Desktop collapse button */}
          <button
            onClick={onToggleCollapse}
            className="hidden lg:flex p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-900 transition-colors"
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>

          {/* Mobile close button */}
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-900 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Workspace Switcher */}
        {!isCollapsed && (
          <button
            onClick={onOpenAuthModal}
            className="w-full flex items-center justify-between p-2.5 rounded-xl bg-neutral-900/80 hover:bg-neutral-900 border border-neutral-800 text-xs text-neutral-300 hover:border-neutral-700 transition-all text-left group"
          >
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-lg bg-neutral-800 flex items-center justify-center shrink-0 text-amber-400">
                <Briefcase className="w-3.5 h-3.5" />
              </div>
              <div className="truncate">
                <div className="font-semibold text-white truncate text-xs">
                  {activeWorkspace?.name || 'My Workspace'}
                </div>
                <div className="text-[10px] text-neutral-400">
                  {planLabel(entitlements.plan)} Plan • {workspaces.length} Spaces
                </div>
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-neutral-500 group-hover:text-neutral-300 shrink-0 ml-1" />
          </button>
        )}

        {/* Primary Action Button: Process New Video */}
        <button
          id="btn-sidebar-upload"
          onClick={() => {
            onOpenUpload();
            onCloseMobile();
          }}
          className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/15 active:scale-95 transition-all ${
            isCollapsed ? 'px-2' : 'px-4'
          }`}
          title="Repurpose Long Video"
        >
          <Plus className="w-4 h-4 stroke-[2.5] shrink-0" />
          {!isCollapsed && <span>New Video Project</span>}
        </button>
      </div>

      {/* Center: Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3 py-2 pb-6 space-y-6">
        {/* Main Creation Group */}
        <div className="space-y-1">
          {!isCollapsed && (
            <div className="px-3 text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1.5">
              Studio & Clips
            </div>
          )}
          {primaryNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                id={`sidebar-nav-${item.id}`}
                onClick={() => handleNavClick(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs transition-all relative ${
                  isActive
                    ? 'bg-neutral-900 text-white font-bold border border-neutral-800 shadow-sm'
                    : 'text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900/50 font-medium'
                } ${isCollapsed ? 'justify-center px-2' : ''}`}
              >
                {/* Active Indicator Bar */}
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r bg-amber-400" />
                )}
                <Icon
                  className={`w-4 h-4 shrink-0 ${
                    isActive ? 'text-amber-400' : 'text-neutral-400'
                  }`}
                />
                {!isCollapsed && (
                  <div className="flex-1 flex items-center justify-between min-w-0">
                    <span className="truncate">{item.label}</span>
                    {item.badge && (
                      <span
                        className={`text-[10px] px-1.5 py-0.2 rounded font-bold ${
                          isActive
                            ? 'bg-amber-400/20 text-amber-300'
                            : 'bg-neutral-800 text-neutral-400'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Project Folders Quick Switcher (when not collapsed) */}
        {!isCollapsed && (projects.length === 0 ? (
          <div className="space-y-1.5 pt-1">
            <div className="px-3 flex items-center justify-between text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
              <span>Your Project Folders</span>
            </div>
            <div className="space-y-1 pl-1">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg">
                  <Skeleton className="w-3.5 h-3.5 rounded shrink-0" />
                  <Skeleton className="h-3 flex-1" />
                  <Skeleton className="h-3 w-6 rounded shrink-0" />
                </div>
              ))}
            </div>
          </div>
        ) : projects.length > 0 && (
          <div className="space-y-1.5 pt-1">
            <div className="px-3 flex items-center justify-between text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
              <span>Your Project Folders</span>
              <button
                onClick={() => handleNavClick('folders')}
                className="text-amber-400 hover:text-amber-300 font-semibold lowercase text-[10px]"
              >
                view all
              </button>
            </div>

            <div className="space-y-1 pl-1">
              {projects.slice(0, 4).map((p) => {
                const isCurrent = p.id === activeProject?.id;
                const displayName = p.folderName || p.title;
                const isProcessing = p.processingStatus === 'processing';

                return (
                  <button
                    key={p.id}
                    onClick={() => {
                      if (isProcessing || !onSelectProject) return;
                      onSelectProject(p);
                      handleNavClick('generator');
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-all text-left group ${
                      isCurrent
                        ? 'bg-neutral-900 text-amber-300 font-semibold border border-neutral-800'
                        : isProcessing
                        ? 'text-neutral-600 cursor-not-allowed'
                        : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900/40'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <FolderOpen className={`w-3.5 h-3.5 shrink-0 ${isCurrent ? 'text-amber-400' : isProcessing ? 'text-neutral-600' : 'text-neutral-500'}`} />
                      <span className="truncate text-[11px]">{displayName}</span>
                      {isProcessing && (
                        <span className="text-[9px] text-amber-400 animate-pulse">Processing...</span>
                      )}
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-900 text-neutral-400 font-mono shrink-0 ml-1">
                      {p.clips.length}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        {/* Distribution Group */}
        <div className="space-y-1">
          {distributionNavItems.length > 0 && !isCollapsed && (
            <div className="px-3 text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1.5">
              Distribution & Analytics
            </div>
          )}
          {distributionNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                id={`sidebar-nav-${item.id}`}
                onClick={() => handleNavClick(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs transition-all relative ${
                  isActive
                    ? 'bg-neutral-900 text-white font-bold border border-neutral-800 shadow-sm'
                    : 'text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900/50 font-medium'
                } ${isCollapsed ? 'justify-center px-2' : ''}`}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r bg-amber-400" />
                )}
                <Icon
                  className={`w-4 h-4 shrink-0 ${
                    isActive ? 'text-amber-400' : 'text-neutral-400'
                  }`}
                />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </div>

        {/* Customization & Settings Group */}
        <div className="space-y-1 mb-4">
          {!isCollapsed && (
            <div className="px-3 text-[10px] font-bold text-neutral-400 uppercase tracking-wider mb-1.5">
              Settings & Brand
            </div>
          )}
          {settingsNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                id={`sidebar-nav-${item.id}`}
                onClick={() => handleNavClick(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs transition-all relative ${
                  isActive
                    ? 'bg-neutral-900 text-white font-bold border border-neutral-800 shadow-sm'
                    : 'text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900/50 font-medium'
                } ${isCollapsed ? 'justify-center px-2' : ''}`}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r bg-amber-400" />
                )}
                <Icon
                  className={`w-4 h-4 shrink-0 ${
                    isActive ? 'text-amber-400' : 'text-neutral-400'
                  }`}
                />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Section: AI Credits Meter & User Profile */}
      <div className="p-3 border-t border-neutral-900 space-y-3 bg-neutral-950">
        {/* Credits usage widget */}
        {!isCollapsed ? (
          <div className="p-3 rounded-xl bg-neutral-900/70 border border-neutral-800 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-neutral-300 font-semibold text-[11px]">
                <Zap className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                <span>AI Render Quota</span>
              </span>
              <span className="text-[11px] font-mono text-amber-400 font-bold">
                {user.aiCreditsMinutesRemaining}m / {user.aiCreditsTotal}m
              </span>
            </div>
            <div className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded-full transition-all duration-300"
                style={{ width: `${aiCreditPercent}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[10px] text-neutral-400 pt-0.5">
              <span>
                {renewalDays === null
                  ? 'No active billing period'
                  : renewalDays === 0
                  ? 'Resets today'
                  : `Resets in ${renewalDays} day${renewalDays === 1 ? '' : 's'}`}
              </span>
              <button
                onClick={() => handleNavClick('settings')}
                className="text-amber-400 hover:underline font-semibold"
              >
                Upgrade
              </button>
            </div>
          </div>
        ) : (
          <div
            onClick={() => handleNavClick('settings')}
            className="cursor-pointer flex flex-col items-center p-2 rounded-xl bg-neutral-900 border border-neutral-800 text-amber-400 hover:border-amber-500/50 transition-all"
            title={`AI Credits: ${user.aiCreditsMinutesRemaining}m remaining`}
          >
            <Zap className="w-4 h-4 fill-amber-400 mb-0.5" />
            <span className="text-[9px] font-mono font-bold">{user.aiCreditsMinutesRemaining}m</span>
          </div>
        )}

        {/* User Profile Mini Bar */}
        <div
          onClick={onOpenAuthModal}
          className={`cursor-pointer flex items-center p-2 rounded-xl bg-neutral-900/40 hover:bg-neutral-900 border border-transparent hover:border-neutral-800 transition-all ${
            isCollapsed ? 'justify-center p-1' : 'justify-between'
          }`}
          title={`Signed in as ${user.name}`}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            {user.avatarUrl ? (
              <img
                src={user.avatarUrl}
                alt={user.name}
                className="w-8 h-8 rounded-lg object-cover border border-neutral-700 shrink-0"
              />
            ) : (
              <div className="w-8 h-8 rounded-lg bg-neutral-800 border border-neutral-700 shrink-0 flex items-center justify-center text-neutral-400 text-xs font-bold">
                {user.name?.charAt(0)?.toUpperCase()}
              </div>
            )}
            {!isCollapsed && (
              <div className="truncate">
                <div className="font-bold text-white text-xs truncate">{user.name}</div>
                <div className="text-[10px] text-neutral-400 truncate">{user.email}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Left Sidebar */}
      <aside
        className={`hidden lg:flex flex-col shrink-0 border-r border-neutral-800/80 h-screen sticky top-0 transition-all duration-300 z-30 ${
          isCollapsed ? 'w-20' : 'w-64'
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Drawer (Backdrop + Slide-out) */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          {/* Backdrop overlay */}
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobile}
          />

          {/* Drawer content */}
          <div className="relative w-72 max-w-[85vw] h-full shadow-2xl z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
};
