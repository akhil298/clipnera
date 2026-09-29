"use client";
import React from 'react';
import { Bell, Plus, Briefcase, ChevronRight, Crown, Clock, Search, Loader2 } from 'lucide-react';
import { useEntitlements, planLabel, isPaidPlan } from '@/hooks/useEntitlements';
import { Skeleton } from '@/components/skeletons';
import { TabType, UserProfile, Workspace, VideoProject, ViralClip } from '@/lib/types';
import { LogoMark } from '@/components/ui/LogoMark';
import { Avatar } from './Avatar';
import { CreditsPopover } from './CreditsPopover';

interface HeaderProps {
  activeTab: TabType;
  onOpenUpload: () => void;
  user: UserProfile;
  workspaces: Workspace[];
  projects: VideoProject[];
  activeProject?: VideoProject;
  selectedClip?: ViralClip;
  unreadNotificationsCount: number;
  onOpenNotifications: () => void;
  onOpenAuthModal: () => void;
  onOpenCommandPalette: () => void;
  onNavigateTab: (tab: TabType) => void;
  onUpgradePlan?: () => void;
}

const TAB_TITLES: Record<TabType, string> = {
  dashboard: 'Home',
  folders: 'Projects',
  generator: 'Clips',
  editor: 'Edit clip',
  scheduler: 'Scheduler',
  analytics: 'Analytics',
  brand_kit: 'Brand kit',
  reels: 'Reels',
  settings: 'Settings',
};

interface Crumb {
  label: string;
  tab?: TabType;
}

const crumbsFor = (tab: TabType, project?: VideoProject): Crumb[] => {
  const projectName = project?.folderName || project?.title;
  if (tab === 'generator') {
    return [{ label: 'Projects', tab: 'folders' }, { label: projectName || 'Clips' }];
  }
  if (tab === 'editor') {
    return [
      { label: 'Projects', tab: 'folders' },
      ...(projectName ? [{ label: projectName, tab: 'generator' as TabType }] : []),
      { label: 'Edit clip' },
    ];
  }
  return [{ label: TAB_TITLES[tab] }];
};

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onOpenUpload,
  user,
  workspaces,
  projects,
  activeProject,
  selectedClip,
  unreadNotificationsCount,
  onOpenNotifications,
  onOpenAuthModal,
  onOpenCommandPalette,
  onNavigateTab,
  onUpgradePlan,
}) => {
  // Until the real plan arrives, entitlements hold a Free placeholder; showing
  // it made Pro users see "Free" and an Upgrade button for a moment.
  const { entitlements, isLoading: planLoading } = useEntitlements();
  const activeWorkspace = workspaces.find((w) => w.id === user.activeWorkspaceId) || workspaces[0];
  const crumbs = crumbsFor(activeTab, activeProject);
  const processing = projects.filter((p) => p.processingStatus === 'processing');
  const firstJob = processing[0];

  return (
    <header className="sticky top-0 z-20 h-14 md:h-16 w-full shrink-0 border-b border-neutral-800/80 bg-neutral-950/90 backdrop-blur-md px-4 lg:px-6 flex items-center gap-2 sm:gap-3">
      {/* Phone: the brand mark stands in for the sidebar */}
      <button
        type="button"
        onClick={() => onNavigateTab('dashboard')}
        className="md:hidden flex shrink-0"
        aria-label="Clipnera home"
      >
        <LogoMark />
      </button>

      {/* Where you are */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-[13px] min-w-0 flex-1 overflow-hidden">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <React.Fragment key={`${crumb.label}-${i}`}>
              {i > 0 && <ChevronRight className="hidden md:block w-3.5 h-3.5 text-neutral-600 shrink-0" />}
              {isLast ? (
                <span className="font-semibold text-white truncate min-w-0" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => crumb.tab && onNavigateTab(crumb.tab)}
                  className="hidden md:block font-medium text-neutral-400 hover:text-white truncate max-w-[180px] min-w-[3rem] transition-colors"
                >
                  {crumb.label}
                </button>
              )}
            </React.Fragment>
          );
        })}
        {activeTab === 'editor' && selectedClip && (
          <span
            className="hidden xl:inline-flex items-center h-5 px-1.5 rounded-md text-[11px] font-bold bg-amber-500/15 text-amber-300 tabular-nums shrink-0"
            title="Virality score"
          >
            {selectedClip.viralityScore}
          </span>
        )}
      </nav>

      {/* Search */}
      <button
        type="button"
        onClick={onOpenCommandPalette}
        className="hidden sm:flex shrink-0 items-center gap-2 w-9 lg:w-56 xl:w-72 h-9 px-2.5 lg:px-3 rounded-xl border border-neutral-800 bg-neutral-900/60 text-neutral-500 hover:text-neutral-300 hover:border-neutral-700 transition-colors justify-center lg:justify-start"
        aria-label="Search projects, clips and actions"
        aria-keyshortcuts="Meta+K Control+K"
      >
        <Search className="w-4 h-4 shrink-0" />
        <span className="hidden lg:inline flex-1 text-left text-[13px] truncate">Search projects, clips, actions</span>
        <kbd className="hidden lg:inline font-mono text-[10.5px] px-1.5 py-0.5 rounded-md border border-neutral-700 bg-neutral-900 text-neutral-400">
          ⌘K
        </kbd>
      </button>
      <button
        type="button"
        onClick={onOpenCommandPalette}
        className="sm:hidden p-2 rounded-xl text-neutral-300 hover:text-white"
        aria-label="Search"
      >
        <Search className="w-[18px] h-[18px]" />
      </button>

      <div className="flex items-center gap-2 shrink-0">
        {/* Background jobs: what is processing right now */}
        {firstJob && (
          <button
            type="button"
            onClick={() => onNavigateTab('folders')}
            className="flex items-center gap-2 h-9 px-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs font-semibold hover:border-amber-500/50 transition-colors"
            title={processing.map((p) => `${p.folderName || p.title}: ${Math.round(p.processingProgress || 0)}%`).join('\n')}
          >
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span className="hidden xl:inline max-w-[140px] truncate">{firstJob.folderName || firstJob.title}</span>
            <span className="tabular-nums">{Math.round(firstJob.processingProgress || 0)}%</span>
            {processing.length > 1 && <span className="text-amber-400/80">+{processing.length - 1}</span>}
          </button>
        )}

        {/* Workspace */}
        <button
          type="button"
          onClick={onOpenAuthModal}
          className="hidden 2xl:flex items-center gap-1.5 h-9 px-2.5 rounded-xl bg-neutral-900 border border-neutral-800 text-xs text-neutral-300 hover:text-white hover:border-neutral-700 transition-colors"
          title="Switch workspace"
        >
          <Briefcase className="w-3.5 h-3.5 text-amber-400" />
          <span className="max-w-[120px] truncate font-medium">{activeWorkspace?.name || 'Workspace'}</span>
        </button>

        {/* Current plan */}
        {planLoading ? (
          <Skeleton className="hidden md:block h-9 w-16 rounded-xl" />
        ) : (
          <button
            type="button"
            onClick={() => onNavigateTab('settings')}
            className={`hidden md:flex items-center gap-1.5 h-9 px-2.5 rounded-xl border text-xs font-bold transition-colors ${
              isPaidPlan(entitlements)
                ? 'bg-amber-500/10 border-amber-500/25 text-amber-300 hover:border-amber-500/50'
                : 'bg-neutral-900 border-neutral-800 text-neutral-400 hover:border-neutral-700'
            }`}
            title={`You are on the ${planLabel(entitlements.plan)} plan`}
          >
            {isPaidPlan(entitlements) && <Crown className="w-3.5 h-3.5" />}
            <span>{planLabel(entitlements.plan)}</span>
          </button>
        )}

        <CreditsPopover
          remaining={user.aiCreditsMinutesRemaining}
          total={user.aiCreditsTotal}
          onManagePlan={onUpgradePlan || (() => onNavigateTab('settings'))}
        />

        {/* Free plan: upgrade, or the pending state once they have paid */}
        {!planLoading && !isPaidPlan(entitlements) && entitlements.has_pending_payment && (
          <span
            className="hidden lg:flex items-center gap-1.5 h-9 px-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-bold"
            title="We'll switch your plan as soon as your payment is approved"
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Pro activation pending</span>
          </span>
        )}
        {!planLoading && !isPaidPlan(entitlements) && !entitlements.has_pending_payment && (
          <button
            type="button"
            onClick={onUpgradePlan || (() => onNavigateTab('settings'))}
            className="hidden lg:flex items-center gap-1.5 h-9 px-3 rounded-xl border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 text-xs font-bold transition-colors"
          >
            <Crown className="w-3.5 h-3.5" />
            <span>Upgrade</span>
          </button>
        )}

        <button
          type="button"
          onClick={onOpenNotifications}
          className="relative flex items-center justify-center w-9 h-9 rounded-xl sm:bg-neutral-900 sm:border border-neutral-800 text-neutral-300 hover:text-white hover:border-neutral-700 transition-colors"
          aria-label={
            unreadNotificationsCount > 0 ? `Notifications, ${unreadNotificationsCount} unread` : 'Notifications'
          }
        >
          <Bell className="w-4 h-4" />
          {unreadNotificationsCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-amber-500 text-[9px] font-bold text-neutral-950">
              {unreadNotificationsCount > 9 ? '9+' : unreadNotificationsCount}
            </span>
          )}
        </button>

        {/* The phone tab bar has its own Create button */}
        <button
          id="btn-header-upload"
          type="button"
          onClick={onOpenUpload}
          className="hidden md:flex items-center gap-1.5 h-9 px-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/20 active:scale-[0.98] transition-all"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>New video</span>
        </button>

        <button
          type="button"
          onClick={onOpenAuthModal}
          className="hidden sm:block p-0.5 rounded-xl border border-neutral-700 hover:border-amber-400 transition-colors"
          title={`Signed in as ${user.name}`}
          aria-label="Account and workspaces"
        >
          <Avatar initials={user.avatarInitials} src={user.avatarUrl} alt={user.name} className="w-7 h-7 text-[11px]" />
        </button>
      </div>
    </header>
  );
};
