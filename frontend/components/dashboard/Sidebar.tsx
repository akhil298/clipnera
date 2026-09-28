"use client";
import React from 'react';
import {
  Sparkles,
  Scissors,
  Film,
  CalendarDays,
  Plus,
  Zap,
  Palette,
  Settings,
  Home,
  Briefcase,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Folder,
  X,
  ShieldCheck,
  Users,
  CreditCard,
  Coins,
  Share2,
  Cpu,
  Clapperboard,
} from 'lucide-react';
import Link from 'next/link';
import { TabType, UserProfile, Workspace, VideoProject, ViralClip } from '@/lib/types';
import { Skeleton } from '@/components/skeletons';
import { useEntitlements, planLabel, creditResetLabel } from '@/hooks/useEntitlements';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { projectStatus, statusDotClass } from '@/components/ui/StatusPill';
import { Avatar } from './Avatar';

interface SidebarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  onOpenUpload: () => void;
  user: UserProfile;
  workspaces: Workspace[];
  projects?: VideoProject[];
  projectsLoading?: boolean;
  activeProject?: VideoProject;
  onSelectProject?: (project: VideoProject) => void;
  selectedClip?: ViralClip;
  onOpenAuthModal: () => void;
  /** Opens Settings on the Plan & billing tab. */
  onOpenBilling?: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

interface NavItem {
  id: TabType;
  label: string;
  icon: React.FC<{ className?: string }>;
  badge?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  onOpenUpload,
  user,
  workspaces,
  projects = [],
  projectsLoading = false,
  activeProject,
  onSelectProject,
  selectedClip,
  onOpenAuthModal,
  onOpenBilling,
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
}) => {
  const { entitlements, isLoading: planLoading } = useEntitlements();
  const { flags } = useFeatureFlags();
  const activeWorkspace = workspaces.find((w) => w.id === user.activeWorkspaceId) || workspaces[0];

  const createItems: NavItem[] = [
    { id: 'dashboard', label: 'Home', icon: Home },
    { id: 'folders', label: 'Projects', icon: Folder, badge: projects.length ? `${projects.length}` : undefined },
    // Shown while an admin has Reels from Images switched on.
    ...(flags['broll_studio.reels'] ? [{ id: 'reels' as TabType, label: 'Reels from images', icon: Clapperboard }] : []),
  ];

  // Clips and the editor only make sense with a project open, so they sit
  // under that project instead of pretending to be top-level pages.
  const projectItems: NavItem[] = [
    {
      id: 'generator',
      label: 'Clips',
      icon: Sparkles,
      badge: activeProject?.clips?.length ? `${activeProject.clips.length}` : undefined,
    },
    { id: 'editor', label: 'Edit clip', icon: Scissors, badge: selectedClip ? 'Open' : undefined },
  ];

  // Shown while an admin has social publishing switched on.
  const publishItems: NavItem[] = flags.social_publishing
    ? [{ id: 'scheduler', label: 'Scheduler', icon: CalendarDays }]
    : [];

  const accountItems: NavItem[] = [
    { id: 'brand_kit', label: 'Brand kit', icon: Palette },
    { id: 'settings', label: 'Settings & billing', icon: Settings },
  ];

  // Same pages as the admin panel's own tabs (components/admin/AdminLayout.tsx).
  const adminNavItems = [
    { href: '/admin/overview', label: 'Overview', icon: ShieldCheck },
    { href: '/admin/users', label: 'Users', icon: Users },
    { href: '/admin/payments', label: 'Payments', icon: CreditCard },
    { href: '/admin/credits', label: 'Credits', icon: Coins },
    { href: '/admin/social', label: 'Social accounts', icon: Share2 },
    { href: '/admin/usage', label: 'AI usage', icon: Cpu },
  ];

  const handleNavClick = (tab: TabType) => {
    onTabChange(tab);
    onCloseMobile();
  };

  const openBilling = () => {
    (onOpenBilling ?? (() => onTabChange('settings')))();
    onCloseMobile();
  };

  // Plan credits and bought credits share one bar so the split is visible.
  const total = Math.max(user.aiCreditsTotal, user.aiCreditsMinutesRemaining, 1);
  const bought = Math.min(entitlements.purchased_credits_remaining, user.aiCreditsMinutesRemaining);
  const planPercent = Math.max(0, ((user.aiCreditsMinutesRemaining - bought) / total) * 100);
  const boughtPercent = Math.max(0, (bought / total) * 100);

  const groupLabel = (label: string, collapsed: boolean) =>
    collapsed ? (
      <div className="mx-auto my-2 h-px w-6 bg-neutral-800" aria-hidden="true" />
    ) : (
      <div className="px-3 pt-4 pb-1.5 text-[10.5px] font-bold text-neutral-500 uppercase tracking-[0.08em]">{label}</div>
    );

  const navButton = (item: NavItem, collapsed: boolean, indent = false) => {
    const Icon = item.icon;
    const isActive = activeTab === item.id;
    return (
      <button
        key={item.id}
        id={`sidebar-nav-${item.id}`}
        type="button"
        onClick={() => handleNavClick(item.id)}
        title={collapsed ? item.label : undefined}
        aria-current={isActive ? 'page' : undefined}
        className={`w-full flex items-center gap-3 rounded-lg text-[13px] transition-colors relative ${
          collapsed ? 'justify-center p-2.5' : `px-3 py-2 ${indent ? 'pl-5' : ''}`
        } ${
          isActive
            ? 'bg-neutral-800/80 text-white font-semibold'
            : 'text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900 font-medium'
        }`}
      >
        {isActive && (
          <span className="absolute -left-3 top-2 bottom-2 w-[3px] rounded-r bg-amber-400" aria-hidden="true" />
        )}
        <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-amber-400' : ''}`} />
        {!collapsed && (
          <>
            <span className="flex-1 text-left truncate">{item.label}</span>
            {item.badge && (
              <span className={`text-[11px] tabular-nums ${isActive ? 'text-amber-300' : 'text-neutral-500'}`}>
                {item.badge}
              </span>
            )}
          </>
        )}
      </button>
    );
  };

  const renderContent = (collapsed: boolean, inDrawer = false) => (
    <div className="h-full flex flex-col bg-neutral-950 text-neutral-200 select-none">
      {/* Brand, workspace and the primary action */}
      <div className={`space-y-3 ${collapsed ? 'p-3' : 'p-4'}`}>
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between'}`}>
          <button
            type="button"
            onClick={() => handleNavClick('dashboard')}
            className="flex items-center gap-2.5 group"
            title="Clipnera home"
          >
            <span className="flex items-center justify-center w-8 h-8 rounded-[10px] bg-gradient-to-br from-amber-300 via-amber-500 to-amber-600 text-neutral-950 shadow-md shadow-amber-500/20 group-hover:scale-105 transition-transform shrink-0">
              <Film className="w-4 h-4 stroke-[2.4]" />
            </span>
            {!collapsed && (
              <span className="flex items-center gap-1.5">
                <span className="font-extrabold text-[17px] tracking-tight text-white">
                  Clip<span className="text-amber-400">nera</span>
                </span>
                {!planLoading && (
                  <span className="px-1.5 py-px text-[9px] font-bold rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 uppercase">
                    {planLabel(entitlements.plan)}
                  </span>
                )}
              </span>
            )}
          </button>

          {!collapsed && !inDrawer && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden lg:flex p-1.5 rounded-lg text-neutral-500 hover:text-white hover:bg-neutral-900 transition-colors"
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          )}
          {inDrawer && (
            <button
              type="button"
              onClick={onCloseMobile}
              className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-900 transition-colors"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {!collapsed && (
          <button
            type="button"
            onClick={onOpenAuthModal}
            className="w-full flex items-center gap-2.5 p-2 rounded-xl bg-neutral-900/70 hover:bg-neutral-900 border border-neutral-800 hover:border-neutral-700 transition-colors text-left group"
          >
            <span className="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
              <Briefcase className="w-3.5 h-3.5" />
            </span>
            <span className="flex-1 min-w-0">
              <span className="block font-semibold text-white truncate text-[12.5px]">
                {activeWorkspace?.name || 'My workspace'}
              </span>
              <span className="block text-[11px] text-neutral-500">
                {planLoading ? '…' : `${planLabel(entitlements.plan)} plan`} · {workspaces.length}{' '}
                {workspaces.length === 1 ? 'workspace' : 'workspaces'}
              </span>
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-neutral-500 group-hover:text-neutral-300 shrink-0" />
          </button>
        )}

        <button
          id={inDrawer ? undefined : collapsed ? undefined : 'btn-sidebar-upload'}
          type="button"
          onClick={() => {
            onOpenUpload();
            onCloseMobile();
          }}
          className={`w-full flex items-center justify-center gap-2 h-9 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-[13px] shadow-md shadow-amber-500/20 active:scale-[0.98] transition-all ${
            collapsed ? 'px-0' : 'px-4'
          }`}
          title="New video"
        >
          <Plus className="w-4 h-4 stroke-[2.5] shrink-0" />
          {!collapsed && <span>New video</span>}
        </button>
      </div>

      {/* Navigation */}
      <nav
        aria-label="Main"
        className={`flex-1 overflow-y-auto pb-4 ${collapsed ? 'px-2' : 'px-3'} [scrollbar-width:thin]`}
      >
        {groupLabel('Create', collapsed)}
        <div className="space-y-0.5">{createItems.map((item) => navButton(item, collapsed))}</div>

        {activeProject && (
          <>
            {collapsed ? (
              groupLabel('Project', true)
            ) : (
              <div className="px-3 pt-4 pb-1.5 flex items-center gap-2 min-w-0">
                <span
                  className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusDotClass(projectStatus(activeProject).tone)}`}
                />
                <span className="text-[10.5px] font-bold text-neutral-500 uppercase tracking-[0.08em] truncate">
                  {activeProject.folderName || activeProject.title}
                </span>
              </div>
            )}
            <div className="space-y-0.5">{projectItems.map((item) => navButton(item, collapsed, true))}</div>
          </>
        )}

        {publishItems.length > 0 && (
          <>
            {groupLabel('Publish', collapsed)}
            <div className="space-y-0.5">{publishItems.map((item) => navButton(item, collapsed))}</div>
          </>
        )}

        {groupLabel('Brand & account', collapsed)}
        <div className="space-y-0.5">{accountItems.map((item) => navButton(item, collapsed))}</div>

        {/* Recent projects */}
        {!collapsed &&
          (projectsLoading ? (
            <div className="pt-2">
              {groupLabel('Recent projects', false)}
              <div className="space-y-1">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-1.5">
                    <Skeleton className="w-2 h-2 rounded-full shrink-0" />
                    <Skeleton className="h-3 flex-1" />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            projects.length > 0 && (
              <div className="pt-2">
                <div className="px-3 pt-4 pb-1.5 flex items-center justify-between">
                  <span className="text-[10.5px] font-bold text-neutral-500 uppercase tracking-[0.08em]">
                    Recent projects
                  </span>
                  <button
                    type="button"
                    onClick={() => handleNavClick('folders')}
                    className="text-[11px] font-semibold text-amber-400 hover:text-amber-300"
                  >
                    View all
                  </button>
                </div>
                <div className="space-y-0.5">
                  {projects.slice(0, 4).map((p) => {
                    const isCurrent = p.id === activeProject?.id;
                    const isProcessing = p.processingStatus === 'processing';
                    const status = projectStatus(p);
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => {
                          // A project still processing has no clips to open yet;
                          // its progress lives on the Projects page.
                          if (isProcessing || !onSelectProject) {
                            handleNavClick('folders');
                            return;
                          }
                          onSelectProject(p);
                          onCloseMobile();
                        }}
                        title={`${p.folderName || p.title} · ${status.label}`}
                        className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-[12.5px] text-left transition-colors ${
                          isCurrent ? 'bg-neutral-900 text-white' : 'text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900'
                        }`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusDotClass(status.tone)}`} />
                        <span className="flex-1 truncate">{p.folderName || p.title}</span>
                        <span className="text-[11px] tabular-nums text-neutral-500 shrink-0">
                          {isProcessing ? `${Math.round(p.processingProgress || 0)}%` : p.clips.length}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )
          ))}

        {/* Admin: only for platform admins; the API checks the role again. */}
        {user.role === 'admin' && (
          <>
            {groupLabel('Admin', collapsed)}
            <div className="space-y-0.5">
              {adminNavItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onCloseMobile}
                    title={collapsed ? item.label : undefined}
                    className={`w-full flex items-center gap-3 rounded-lg text-[13px] font-medium text-neutral-400 hover:text-neutral-100 hover:bg-neutral-900 transition-colors ${
                      collapsed ? 'justify-center p-2.5' : 'px-3 py-2'
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0 text-violet-400" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          </>
        )}
      </nav>

      {/* Credits and the signed-in user */}
      <div className={`border-t border-neutral-900 space-y-2 ${collapsed ? 'p-2' : 'p-3'} pb-[max(0.75rem,env(safe-area-inset-bottom))]`}>
        {collapsed ? (
          <button
            type="button"
            onClick={openBilling}
            className="w-full flex flex-col items-center gap-0.5 py-2 rounded-xl bg-neutral-900 border border-neutral-800 text-amber-400 hover:border-amber-500/50 transition-colors"
            title={`${user.aiCreditsMinutesRemaining} credits left`}
          >
            <Zap className="w-4 h-4 fill-amber-400" />
            <span className="text-[10px] font-bold tabular-nums">{user.aiCreditsMinutesRemaining}</span>
          </button>
        ) : (
          <div className="p-3 rounded-xl bg-neutral-900/70 border border-neutral-800 space-y-2">
            <div className="flex items-baseline justify-between text-xs">
              <span className="text-neutral-400 font-medium">Credits</span>
              <span className="font-bold text-white tabular-nums">
                {user.aiCreditsMinutesRemaining}
                <span className="text-neutral-500 font-medium"> / {user.aiCreditsTotal}</span>
              </span>
            </div>
            <div
              className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden flex"
              role="img"
              aria-label={`${user.aiCreditsMinutesRemaining} of ${user.aiCreditsTotal} credits left${bought ? `, including ${bought} bought credits` : ''}`}
            >
              <div className="h-full bg-amber-500 transition-all duration-300" style={{ width: `${planPercent}%` }} />
              <div className="h-full bg-violet-400 transition-all duration-300" style={{ width: `${boughtPercent}%` }} />
            </div>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-neutral-500">{creditResetLabel(entitlements.next_credit_reset_at)}</span>
              <button type="button" onClick={openBilling} className="text-amber-400 hover:text-amber-300 font-semibold">
                Buy credits
              </button>
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={onOpenAuthModal}
          className={`w-full flex items-center gap-2.5 p-1.5 rounded-xl hover:bg-neutral-900 transition-colors text-left ${
            collapsed ? 'justify-center' : ''
          }`}
          title={`Signed in as ${user.name}`}
        >
          <Avatar initials={user.avatarInitials} src={user.avatarUrl} alt={user.name} className="w-8 h-8 shrink-0 text-xs" />
          {!collapsed && (
            <span className="min-w-0 flex-1">
              <span className="block font-semibold text-white text-[12.5px] truncate">{user.name}</span>
              <span className="block text-[11px] text-neutral-500 truncate">{user.email}</span>
            </span>
          )}
        </button>

        {collapsed && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden lg:flex w-full justify-center p-1.5 rounded-lg text-neutral-500 hover:text-white hover:bg-neutral-900 transition-colors"
            title="Expand sidebar"
            aria-label="Expand sidebar"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Tablet: an icon rail, always compact */}
      <aside className="hidden md:flex lg:hidden flex-col shrink-0 w-[72px] border-r border-neutral-800/80 h-[100dvh] sticky top-0 z-30">
        {renderContent(true)}
      </aside>

      {/* Desktop: full sidebar, collapsible */}
      <aside
        className={`hidden lg:flex flex-col shrink-0 border-r border-neutral-800/80 h-[100dvh] sticky top-0 transition-[width] duration-300 z-30 ${
          isCollapsed ? 'w-[76px]' : 'w-64'
        }`}
      >
        {renderContent(isCollapsed)}
      </aside>

      {/* Phone and tablet: the full menu as a drawer, opened from "More" */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm" onClick={onCloseMobile} />
          <div className="relative w-72 max-w-[85vw] h-full shadow-2xl z-10 animate-in slide-in-from-left duration-200 border-r border-neutral-800">
            {renderContent(false, true)}
          </div>
        </div>
      )}
    </>
  );
};
