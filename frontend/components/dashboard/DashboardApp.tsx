"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams, usePathname } from 'next/navigation';
import { Trash2 } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { UploadModal } from './UploadModal';
import { DashboardHomeView } from './DashboardHomeView';
import { ProjectFoldersView } from './ProjectFoldersView';
import { ClipGeneratorView } from './ClipGeneratorView';
import { VideoEditorStudio } from './VideoEditorStudio';
import { SocialSchedulerView } from './SocialSchedulerView';
import { ViralAnalyticsView } from './ViralAnalyticsView';
import { BrandKitView } from './BrandKitView';
import { ReelsView } from './ReelsView';
import { SettingsView } from './SettingsView';
import { NotificationsDrawer } from './NotificationsDrawer';
import { SnackbarStack } from './SnackbarStack';
import { AuthModal } from './AuthModal';
import { PlanSelectionModal, type SelectedPlan } from './PlanSelectionModal';
import { PlanBanner } from './PlanBanner';
import { EntitlementsProvider } from './EntitlementsProvider';
import { PaymentModal } from './PaymentModal';
import { VideoProject, ViralClip, TabType, UserProfile, Workspace, AppNotification, PipelineStep, PipelineStatus } from '@/lib/types';
import { DashboardSkeleton } from '@/components/skeletons';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { useNotificationInbox } from '@/hooks/useNotificationInbox';
import { userApi, workspaceApi, authApi, pipelineApi, subscriptionApi, clipApi, mapBackendClip } from '@/lib/api';
import { isAuthenticated, clearAuth } from '@/lib/auth';
import { youtubeThumbnailUrl } from '@/lib/utils/urlParser';
import type { UserProfileResponse } from '@/lib/api';

const toUserProfile = (profile: UserProfileResponse, fallbackWorkspaceId: string): UserProfile => ({
  id: profile.id,
  name: profile.name,
  email: profile.email,
  avatarUrl: profile.avatar_url || '',
  avatarInitials: profile.avatar_initials,
  plan: profile.plan as UserProfile['plan'],
  aiCreditsMinutesRemaining: profile.ai_credits_minutes_remaining,
  aiCreditsTotal: profile.ai_credits_total,
  activeWorkspaceId: profile.active_workspace_id || fallbackWorkspaceId,
  providers: profile.providers,
  role: profile.role,
});

const getTabFromPathname = (pathname: string): TabType => {
  const segments = pathname.split('/').filter(Boolean);

  if (segments[0] !== 'dashboard') return 'dashboard';
  if (segments[1] === 'folders') return 'folders';
  if (segments[1] === 'projects' && segments[2]) {
    if (segments[3] === 'edit' && segments[4]) return 'editor';
    return 'generator';
  }
  if (segments[1] === 'scheduler') return 'scheduler';
  if (segments[1] === 'analytics') return 'analytics';
  if (segments[1] === 'brand-kit') return 'brand_kit';
  if (segments[1] === 'reels') return 'reels';
  if (segments[1] === 'settings') return 'settings';

  return 'dashboard';
};

const getDashboardPath = (
  tab: TabType,
  projectId?: string,
  clipId?: string,
) => {
  switch (tab) {
    case 'folders':
      return '/dashboard/folders';
    case 'generator':
      return projectId ? `/dashboard/projects/${encodeURIComponent(projectId)}` : '/dashboard/folders';
    case 'editor':
      return projectId && clipId
        ? `/dashboard/projects/${encodeURIComponent(projectId)}/edit/${encodeURIComponent(clipId)}`
        : projectId
          ? `/dashboard/projects/${encodeURIComponent(projectId)}`
          : '/dashboard/folders';
    case 'scheduler':
      return '/dashboard/scheduler';
    case 'analytics':
      return '/dashboard/analytics';
    case 'brand_kit':
      return '/dashboard/brand-kit';
    case 'reels':
      return '/dashboard/reels';
    case 'settings':
      return '/dashboard/settings';
    case 'dashboard':
    default:
      return '/dashboard';
  }
};

export default function DashboardApp() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams<{ projectId?: string; clipId?: string; reelId?: string }>();
  const routeProjectId = typeof params.projectId === 'string' ? params.projectId : undefined;
  const routeClipId = typeof params.clipId === 'string' ? params.clipId : undefined;
  const routeReelId = typeof params.reelId === 'string' ? params.reelId : undefined;

  // Auth gate: only authenticated users may view the dashboard.
  const [isAuthed, setIsAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/');
    } else {
      setIsAuthed(true);
    }
  }, [router]);

  // Navigation State
  const activeTab = getTabFromPathname(pathname);
  const [activeSettingsTab, setActiveSettingsTab] = useState<'account' | 'billing' | 'social' | 'team'>('account');
  const { flags } = useFeatureFlags();

  // Deep links such as /dashboard/settings?tab=social (where connecting an
  // account returns to). Read after mount so the server render matches, and
  // on every route change since the shell stays mounted across tabs.
  useEffect(() => {
    const tab = new URLSearchParams(window.location.search).get('tab');
    if (tab === 'billing' || tab === 'social' || tab === 'team') setActiveSettingsTab(tab);
  }, [pathname]);

  // Projects State
  const [projects, setProjects] = useState<VideoProject[]>([]);
  // Distinguishes "still fetching" from "user has no projects" for skeletons.
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [activeProject, setActiveProject] = useState<VideoProject | undefined>(undefined);
  const [selectedClip, setSelectedClip] = useState<ViralClip | undefined>(undefined);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [isAudioReverted, setIsAudioReverted] = useState(false);

  const navigateToTab = useCallback((tab: TabType, projectId?: string, clipId?: string) => {
    const resolvedProjectId = projectId ?? (
      tab === 'generator' || tab === 'editor' || tab === 'scheduler'
        ? activeProject?.id
        : undefined
    );
    const resolvedClipId = clipId ?? (
      tab === 'editor' || tab === 'scheduler'
        ? selectedClip?.id
        : undefined
    );

    router.push(getDashboardPath(tab, resolvedProjectId, resolvedClipId));
  }, [activeProject?.id, router, selectedClip?.id]);

  // Sidebar Layout State
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // User, Workspaces & Notifications
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);

  // Notifications State
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [snackbars, setSnackbars] = useState<AppNotification[]>([]);
  const {
    notifications,
    pushLocal: pushNotification,
    markAllRead: handleMarkAllRead,
    clearAll: handleClearNotifications,
  } = useNotificationInbox(Boolean(isAuthed), (notification) => {
    setSnackbars((prev) => [...prev, notification].slice(-3));
    // The status poll only follows the open project, so reflect the outcome
    // here for every other one too.
    if (notification.projectId) {
      handleUpdateProject(
        notification.projectId,
        notification.type === 'render_failed'
          ? { processingStatus: 'failed' }
          : { processingStatus: 'completed', processingProgress: 100 },
      );
    }
  });
  const dismissSnackbar = useCallback((id: string) => {
    setSnackbars((prev) => prev.filter((n) => n.id !== id));
  }, []);

  // Auth / Workspace Modal
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Plan & Payment modals state
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);
  // Bumped whenever the plan may have changed, so entitlements refetch.
  const [entitlementsRefreshKey, setEntitlementsRefreshKey] = useState(0);
  const [upgradeReason, setUpgradeReason] = useState<string | undefined>(undefined);

  // Opens the plan modal from anywhere a locked control is clicked.
  const promptUpgrade = useCallback((reason?: string) => {
    setUpgradeReason(reason);
    setIsPlanModalOpen(true);
  }, []);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<SelectedPlan | null>(null);

  // Delete confirmation modal
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  useEffect(() => {
    if (!routeProjectId || projects.length === 0) return;

    const routeProject = projects.find((project) => project.id === routeProjectId);
    if (routeProject) {
      setActiveProject(routeProject);
      if (routeClipId) {
        const routeClip = routeProject.clips.find((clip) => clip.id === routeClipId);
        if (routeClip) setSelectedClip(routeClip);
      }
    } else {
      router.replace('/dashboard/folders');
    }
  }, [routeProjectId, routeClipId, projects, router]);

  // Fetch real user profile and workspaces on mount
  useEffect(() => {
    if (!isAuthed) return;
    let cancelled = false;

    async function loadData() {
      try {
        const [profile, wsList, projectResponse] = await Promise.all([
          userApi.getMe(),
          workspaceApi.list(),
          clipApi.listProjects(),
        ]);
        if (cancelled) return;
        setCurrentUser(toUserProfile(profile, wsList[0]?.id || ''));
        setWorkspaces(
          wsList.map((ws) => ({
            id: ws.id,
            name: ws.name,
            role: ws.role as Workspace['role'],
            membersCount: ws.member_count,
          }))
        );
        // Build a project from its row plus (optionally) its pipeline status.
        // Status is applied separately so the list can paint before it arrives.
        const buildProject = (
          project: (typeof projectResponse.projects)[number],
          pipelineStatus: PipelineStatus | null,
        ): VideoProject => {
          const clips = (project.clips || []).map(mapBackendClip);
          // The pipeline's own view wins when there is one. Going by
          // project.status alone left a project whose run had finished but
          // whose row still said "uploaded" showing as processing forever.
          const hasPipeline = Boolean(pipelineStatus?.steps?.length);
          const failed = Boolean(pipelineStatus?.error) || project.status === 'failed';
          const processing = failed
            ? false
            : hasPipeline
              ? !pipelineStatus!.is_completed
              : ['processing', 'pending', 'uploaded'].includes(project.status);
          const completedSteps = (pipelineStatus?.steps || []).filter(
            (step: PipelineStep) => step.status === 'completed' || step.status === 'skipped',
          ).length;
          const progress = pipelineStatus?.is_completed
            ? 100
            : hasPipeline
              ? Math.round((completedSteps / pipelineStatus!.steps.length) * 100)
              : 0;
          const youtubeThumbnail = youtubeThumbnailUrl(project.source_url || '');
          const uploaded = project.source_type === 'upload';
          return {
            id: project.id,
            title: project.title,
            folderName: project.title,
            folderCategory: uploaded ? ('Upload' as const) : ('YouTube Ingest' as const),
            folderColor: 'amber' as const,
            sourceUrl: project.source_url || '',
            sourceChannel: uploaded ? 'Upload' : 'YouTube',
            description: processing ? 'Processing video and generating clips...' : 'AI analysis completed. Clips generated with kinetic captions.',
            tags: [uploaded ? 'Upload' : 'YouTube', 'AI', 'Shorts'],
            genre: uploaded ? 'Upload' : 'YouTube Ingest',
            duration: project.duration_seconds || 0,
            sourceType: uploaded ? ('upload' as const) : ('youtube_url' as const),
            videoUrl: '',
            posterUrl: clips[0]?.posterUrl || youtubeThumbnail || '',
            uploadedAt: project.created_at || new Date().toISOString(),
            syncStatus: project.status === 'uploaded' ? 'synced' as const : 'syncing' as const,
            offlineAvailable: project.status === 'uploaded',
            clips,
            transcript: [],
            processingProgress: progress,
            processingStatus: failed
              ? 'failed' as const
              : processing ? 'processing' as const : 'completed' as const,
            aiCostUsd: project.ai_cost_usd,
          } satisfies VideoProject;
        };

        // Paint the list from the project rows alone. Previously this awaited
        // one status request per project before rendering anything, so the
        // dashboard stayed blank until the slowest of N requests came back.
        const baseProjects = projectResponse.projects.map((project) => buildProject(project, null));
        setProjects(baseProjects);
        setProjectsLoaded(true);
        const initialProject = routeProjectId
          ? baseProjects.find((project) => project.id === routeProjectId)
          : baseProjects[0];
        if (initialProject) {
          setActiveProject(initialProject);
        }

        // Then refine with real pipeline state in a single batched request.
        if (baseProjects.length > 0) {
          try {
            const { statuses } = await pipelineApi.getStatusBatch(baseProjects.map((p) => p.id));
            if (cancelled) return;
            const refined = projectResponse.projects.map((project) =>
              buildProject(project, statuses[project.id] ?? null),
            );
            // The list rows carry clip summaries without video URLs. If the
            // full clips already loaded, overwriting them here would leave the
            // cards on "Render still processing" with nothing left to refetch.
            const keepLoadedClips = (next: VideoProject, prev?: VideoProject): VideoProject =>
              prev?.clips.some((clip) => clip.presignedUrl) ? { ...next, clips: prev.clips } : next;
            setProjects((prevProjects) =>
              refined.map((project) =>
                keepLoadedClips(project, prevProjects.find((p) => p.id === project.id)),
              ),
            );
            setActiveProject((prev) => {
              const next = prev && refined.find((p) => p.id === prev.id);
              return next ? keepLoadedClips(next, prev) : prev;
            });
          } catch {
            // The list is already usable without pipeline detail.
          }
        }
      } catch (err) {
        if (err instanceof Error && err.message.startsWith('Unauthorized:')) {
          clearAuth();
          router.replace('/');
        }
      } finally {
        if (!cancelled) setProjectsLoaded(true);
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, [isAuthed]);

  useEffect(() => {
    const projectId = activeProject?.id;
    if (!projectId || activeProject.processingStatus === 'failed') return;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let clipsFetchRequested = false;
    const MAX_CLIP_FETCH_RETRIES = 3;

    const fetchClips = async (attempt: number) => {
      try {
        const clipResponse = await clipApi.listClips(projectId);
        if (cancelled) return;
        const mappedClips = (clipResponse.clips || []).map(mapBackendClip);
        handleUpdateProject(projectId, { clips: mappedClips });
        if (mappedClips.length > 0) {
          setSelectedClip((prev) => prev ?? mappedClips[0]);
        }
      } catch (clipErr) {
        console.error('Failed to fetch clips:', clipErr);
        // One failed request used to leave every card on "Render still
        // processing" until a full page reload.
        if (!cancelled && attempt < MAX_CLIP_FETCH_RETRIES) {
          timeoutId = setTimeout(() => void fetchClips(attempt + 1), 2000 * (attempt + 1));
        }
      }
    };

    const loadClipsOnce = () => {
      if (clipsFetchRequested) return;
      clipsFetchRequested = true;
      void fetchClips(0);
    };

    // A finished project has nothing left to watch. This used to keep polling
    // every 3s for the life of the page, holding a DB connection each time and
    // slowing down every other request behind it.
    if (activeProject.processingStatus === 'completed') {
      // The project list carries clip summaries without video URLs, so a
      // non-empty list is not enough: fetch until every clip can play.
      if (activeProject.clips.length === 0 || activeProject.clips.some((clip) => !clip.presignedUrl)) {
        void loadClipsOnce();
      }
      return;
    }

    const applyStatus = (status: PipelineStatus): boolean => {
      setPipelineSteps(status.steps || []);

      if (!status.is_completed && !status.error) {
        if (!status.steps || status.steps.length === 0) return false;
        if (status.steps.every((s) => s.status === 'pending')) return false;

        const runningStep = status.steps.find((s) => s.status === 'running');
        const stepCount = status.steps.length;
        const completedCount = status.steps.filter(
          (s) => s.status === 'completed' || s.status === 'skipped'
        ).length;
        const runningPercent = runningStep?.progress_percent ?? 0;
        const overallPercent = Math.round(
          ((completedCount + runningPercent / 100) / stepCount) * 100
        );

        handleUpdateProject(projectId, {
          processingProgress: overallPercent,
          processingStatus: overallPercent >= 100 ? 'completed' : 'processing',
        });
        return false;
      }

      handleUpdateProject(projectId, {
        processingProgress: 100,
        processingStatus: status.error ? 'failed' : 'completed',
      });
      if (!status.error) void loadClipsOnce();
      return true;
    };

    // Poll only while the run is live, and stop as soon as it settles. Backed
    // off from 3s so a long encode does not hammer the pool for its duration.
    const POLL_MS = 5000;
    const tick = async () => {
      try {
        const status = await pipelineApi.getStatus(projectId);
        if (cancelled) return;
        if (applyStatus(status)) return;
      } catch {
        if (cancelled) return;
        setPipelineSteps([]);
      }
      if (!cancelled) timeoutId = setTimeout(tick, POLL_MS);
    };

    void tick();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [activeProject?.id]);

  const handleRevertPipelineStep = async (step: string) => {
    if (!activeProject?.id || activeProject.processingStatus === 'failed') return;
    try {
      await pipelineApi.revertStep(activeProject.id, step);
      const status = await pipelineApi.getStatus(activeProject.id);
      setPipelineSteps(status.steps || []);
    } catch (err) {
      console.error('Failed to revert step:', err);
    }
  };

  const handleCancelPipeline = async (projectId: string) => {
    try {
      await pipelineApi.cancel(projectId);
    } catch (err) {
      // The server has no live run for it (e.g. after a restart), so there is
      // nothing left to stop; anything else is a real failure to cancel.
      if (!(err instanceof Error && err.message.includes('No active pipeline'))) {
        console.error('Failed to cancel pipeline:', err);
        return;
      }
    }
    handleUpdateProject(projectId, {
      processingStatus: 'failed',
      description: 'Processing was cancelled.',
    });
    if (activeProject?.id === projectId) setPipelineSteps([]);
  };

  // Handle project creation from UploadModal or ProjectFoldersView
  const handleProjectCreated = (newProject: VideoProject) => {
    setProjects([newProject, ...projects]);
    setActiveProject(newProject);
    if (newProject.clips.length > 0) {
      setSelectedClip(newProject.clips[0]);
    }
    // Add notification
    const newNotif: AppNotification = {
      id: `notif-${Date.now()}`,
      title: 'Project Folder Ready',
      message: `Folder "${newProject.folderName || newProject.title}" initialized with ${newProject.clips.length} viral clips.`,
      timestamp: 'Just now',
      read: false,
      type: 'render_complete',
    };
    pushNotification(newNotif);
    navigateToTab(
      newProject.processingStatus === 'processing' ? 'folders' : 'generator',
      newProject.id,
    );
  };

  const handleUpdateProject = (projectId: string, updates: Partial<VideoProject>) => {
    setProjects((prev) =>
      prev.map((p) => (p.id === projectId ? { ...p, ...updates } : p))
    );
    setActiveProject((prev) =>
      prev && prev.id === projectId ? { ...prev, ...updates } : prev
    );
  };

  // Handle opening a folder
  const handleOpenFolder = (project: VideoProject) => {
    setActiveProject(project);
    if (project.clips.length > 0) {
      setSelectedClip(project.clips[0]);
    }
    navigateToTab('generator', project.id);
  };

  // Handle deleting a folder
  const handleDeleteFolder = async (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    const projectName = project?.folderName || project?.title || "Project";
    setDeleteTargetId(projectId);
    setIsDeleteModalOpen(true);
  };

  const confirmDelete = async () => {
    if (!deleteTargetId) return;
    const project = projects.find((p) => p.id === deleteTargetId);
    const projectName = project?.folderName || project?.title || "Project";
    setIsDeleteModalOpen(false);
    setDeleteTargetId(null);

    try {
      if (project?.processingStatus === 'processing') {
        try {
          await pipelineApi.cancel(deleteTargetId);
        } catch {
          // ignore cancel errors
        }
      }
      await clipApi.deleteProject(deleteTargetId);
      const updated = projects.filter((p) => p.id !== deleteTargetId);
      setProjects(updated);
      if (activeProject?.id === deleteTargetId) {
        if (updated.length > 0) {
          setActiveProject(updated[0]);
          if (updated[0].clips.length > 0) {
            setSelectedClip(updated[0].clips[0]);
          }
        } else {
          setActiveProject(undefined);
          setSelectedClip(undefined);
        }
      }
      const newNotif: AppNotification = {
        id: `notif-${Date.now()}`,
        title: 'Project Folder Deleted',
        message: `Folder "${projectName}" and all its clips have been removed.`,
        timestamp: 'Just now',
        read: false,
        type: 'render_complete',
      };
      pushNotification(newNotif);
    } catch (err) {
      console.error('Failed to delete project:', err);
      alert('Failed to delete project. Please try again.');
    }
  };

  // Handle renaming a folder
  const handleRenameFolder = (projectId: string, newName: string) => {
    setProjects((prev) =>
      prev.map((p) => (p.id === projectId ? { ...p, folderName: newName, title: newName } : p))
    );
    if (activeProject?.id === projectId) {
      setActiveProject((prev) => {
        if (!prev) return prev;
        return { ...prev, folderName: newName, title: newName };
      });
    }
  };

  // Handle selecting clip for studio editing
  const handleSelectClipForEdit = (clip: ViralClip) => {
    setSelectedClip(clip);
    navigateToTab('editor', clip.projectId || activeProject?.id, clip.id);
  };

  // Handle scheduling a clip
  const handleScheduleClip = (clip: ViralClip) => {
    setSelectedClip(clip);
    navigateToTab('scheduler', clip.projectId || activeProject?.id, clip.id);
  };

  // Handle selecting a project from dashboard
  const handleSelectProject = (project: VideoProject) => {
    setActiveProject(project);
    if (project.clips.length > 0) {
      setSelectedClip(project.clips[0]);
    }
    navigateToTab('generator', project.id);
  };

  // Update clip after studio edit
  const handleUpdateClip = (updatedClip: ViralClip) => {
    setSelectedClip(updatedClip);
    setActiveProject((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        clips: prev.clips.map((c) => (c.id === updatedClip.id ? updatedClip : c)),
      };
    });
    setProjects((prev) =>
      prev.map((p) =>
        p.id === activeProject?.id
          ? { ...p, clips: p.clips.map((c) => (c.id === updatedClip.id ? updatedClip : c)) }
          : p
      )
    );
  };

  // Switch active workspace
  const handleSelectWorkspace = (workspaceId: string) => {
    setCurrentUser((prev) => prev ? { ...prev, activeWorkspaceId: workspaceId } : prev);
  };

  const navigateToBilling = () => {
    router.push('/dashboard/settings');
    setActiveSettingsTab('billing');
  };

  // Sign out and return to the auth landing page
  const handleSignOut = async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore logout errors
    }
    localStorage.removeItem('token');
    router.replace('/');
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  const handleViewNotificationProject = (notification: AppNotification) => {
    const project = projects.find((p) => p.id === notification.projectId);
    if (project) handleOpenFolder(project);
  };

  const handlePaymentComplete = async () => {
    setIsPaymentModalOpen(false);
    setIsPlanModalOpen(false);
    setSelectedPlan(null);
    setUpgradeReason(undefined);
    // The plan just changed, so the cached capability set is stale.
    setEntitlementsRefreshKey((k) => k + 1);
    let cancelled = false;
    try {
      const profile = await userApi.getMe();
      if (!cancelled) {
        setCurrentUser(toUserProfile(profile, currentUser?.activeWorkspaceId || ''));
      }
    } catch {
      // ignore
    }
    return () => { cancelled = true; };
  };

  const handlePlanSelected = (plan: SelectedPlan) => {
    setSelectedPlan(plan);
    setIsPaymentModalOpen(true);
  };



  if (isAuthed === null || !currentUser) {
    return <DashboardSkeleton />;
  }

  return (
    <EntitlementsProvider
      isAuthed={Boolean(isAuthed)}
      onPromptUpgrade={promptUpgrade}
      refreshKey={entitlementsRefreshKey}
    >
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex font-['Plus_Jakarta_Sans',sans-serif]">
      {/* Left Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={navigateToTab}
        onOpenUpload={() => setIsUploadOpen(true)}
        user={currentUser}
        workspaces={workspaces}
        projects={projects}
        projectsLoading={!projectsLoaded}
        activeProject={activeProject}
        onSelectProject={handleOpenFolder}
        selectedClip={selectedClip}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        isMobileOpen={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Workspace Column */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        {/* Top Header */}
        <Header
          activeTab={activeTab}
          onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
          onOpenUpload={() => setIsUploadOpen(true)}
          user={currentUser}
          workspaces={workspaces}
          activeProject={activeProject}
          selectedClip={selectedClip}
          unreadNotificationsCount={unreadCount}
        onOpenNotifications={() => setIsNotificationsOpen(true)}
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onNavigateTab={navigateToTab}
        onUpgradePlan={navigateToBilling}
      />

        {/* Main View Area */}
        <main className="flex-1 min-h-0 w-full p-4 sm:p-6 lg:p-8">
          <PlanBanner />
          {/* TAB 1: DASHBOARD HOME */}
          {activeTab === 'dashboard' && (
            <DashboardHomeView
              user={currentUser}
              projects={projects}
              workspaces={workspaces}
              activeProject={activeProject}
              onOpenUpload={() => setIsUploadOpen(true)}
              onSelectProject={handleSelectProject}
              onSelectClipForEdit={handleSelectClipForEdit}
              onScheduleClip={handleScheduleClip}
              onNavigateTab={navigateToTab}
              onUpgradePlan={navigateToBilling}
            />
          )}

          {/* TAB 2: PROJECT FOLDERS HUB */}
          {activeTab === 'folders' && (
            <ProjectFoldersView
              projects={projects}
              isLoading={!projectsLoaded}
              activeProject={activeProject}
              onOpenFolder={handleOpenFolder}
              onSelectProject={handleOpenFolder}
              onCreateFolder={handleProjectCreated}
              onDeleteFolder={handleDeleteFolder}
              onRenameFolder={handleRenameFolder}
              onOpenUploadModal={() => setIsUploadOpen(true)}
              onCancelPipeline={handleCancelPipeline}
            />
          )}

          {/* TAB 3: AI CLIPS GENERATOR / FOLDER DETAIL VIEW */}
          {activeTab === 'generator' && (
            <ClipGeneratorView
              project={activeProject || projects[0]}
              onSelectClipForEdit={handleSelectClipForEdit}
              onScheduleClip={handleScheduleClip}
              onOpenUpload={() => setIsUploadOpen(true)}
              onRenameFolder={handleRenameFolder}
              onNavigateTab={navigateToTab}
              pipelineSteps={pipelineSteps}
              onRevertPipelineStep={handleRevertPipelineStep}
              audioBeforeUrl={activeProject?.audioOriginalUrl}
              audioAfterUrl={activeProject?.audioProcessedUrl}
              isAudioReverted={isAudioReverted}
              onRevertAudio={() => {
                if (activeProject?.id) {
                  pipelineApi.revertStep(activeProject.id, 'ai_noise_cancellation').then(() => {
                    setIsAudioReverted(true);
                    handleRevertPipelineStep('ai_noise_cancellation');
                  });
                }
              }}
              onApplyAudio={() => {
                if (activeProject?.id) {
                  pipelineApi.resume(activeProject.id, ['audio_extraction', 'ai_noise_cancellation']).then(() => {
                    setIsAudioReverted(false);
                  });
                }
              }}
            />
          )}

          {/* TAB 4: FULL VIDEO EDITOR STUDIO */}
          {activeTab === 'editor' && (
            <VideoEditorStudio
              clip={selectedClip || activeProject?.clips?.[0] || projects[0]?.clips?.[0]}
              onUpdateClip={handleUpdateClip}
              onBackToGenerator={() => navigateToTab('generator')}
              onScheduleClip={handleScheduleClip}
            />
          )}

          {/* TAB 5: POST TIMING & AI SCHEDULER (shown while social publishing is switched on) */}
          {flags.social_publishing && activeTab === 'scheduler' && (
            <SocialSchedulerView
              clips={activeProject?.clips || projects[0]?.clips || []}
              selectedClip={selectedClip || activeProject?.clips?.[0] || projects[0]?.clips?.[0]}
              onSelectClip={setSelectedClip}
            />
          )}

          {/* TAB 6: VIRAL ANALYTICS & RETENTION ENGINE */}
          {activeTab === 'analytics' && <ViralAnalyticsView />}

          {/* TAB 7: BRAND KIT & SUBTITLE STYLES */}
          {activeTab === 'brand_kit' && <BrandKitView />}

          {activeTab === 'reels' && <ReelsView reelId={routeReelId} />}

          {/* TAB 8: SETTINGS, WORKSPACE & BILLING */}
          {activeTab === 'settings' && currentUser && (
            <SettingsView
              user={currentUser}
              workspaces={workspaces}
              onUpdateUser={setCurrentUser}
              activeSettingsTab={activeSettingsTab}
              onSettingsTabChange={setActiveSettingsTab}
            />
          )}
        </main>
      </div>

      {/* Activity Notifications Drawer */}
      <NotificationsDrawer
        isOpen={isNotificationsOpen}
        onClose={() => setIsNotificationsOpen(false)}
        notifications={notifications}
        onMarkAllRead={handleMarkAllRead}
        onClearAll={handleClearNotifications}
      />

      {/* Snackbars for notifications that arrive while the dashboard is open */}
      <SnackbarStack
        items={snackbars}
        onDismiss={dismissSnackbar}
        onView={handleViewNotificationProject}
      />

      {/* Auth & Workspace Switcher Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        currentUser={currentUser}
        workspaces={workspaces}
        onSelectWorkspace={handleSelectWorkspace}
        onSignOut={handleSignOut}
      />

      {/* Upload & AI Configuration Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onProjectCreated={handleProjectCreated}
      />

      {/* Plan Selection Modal */}
      <PlanSelectionModal
        upgradeReason={upgradeReason}
        isOpen={isPlanModalOpen}
        onClose={() => {
          setIsPlanModalOpen(false);
          setSelectedPlan(null);
          setUpgradeReason(undefined);
        }}
        onPlanSelected={handlePlanSelected}
      />

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg rounded-2xl bg-neutral-900 border border-neutral-800 p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/30">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Delete Project</h3>
                  <p className="text-xs text-neutral-400">This action cannot be undone</p>
                </div>
              </div>
              <button
                onClick={() => { setIsDeleteModalOpen(false); setDeleteTargetId(null); }}
                className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800"
              >
                ✕
              </button>
            </div>
            <p className="text-sm text-neutral-300">
              Are you sure you want to delete <span className="font-semibold text-white">{projects.find(p => p.id === deleteTargetId)?.folderName || 'this project'}</span>?
              <br />
              <span className="text-neutral-400">All clips, videos, and generated content inside this folder will be permanently removed.</span>
            </p>
            <div className="pt-3 border-t border-neutral-800 flex items-center justify-end gap-2.5">
              <button
                onClick={() => { setIsDeleteModalOpen(false); setDeleteTargetId(null); }}
                className="px-4 py-2 rounded-xl bg-neutral-800 text-xs font-medium text-neutral-300 hover:bg-neutral-700"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-5 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-neutral-950 font-bold text-xs shadow-md shadow-rose-500/15"
              >
                Delete Project
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Payment Modal */}
      <PaymentModal
        isOpen={isPaymentModalOpen}
        onClose={() => {
          setIsPaymentModalOpen(false);
          setSelectedPlan(null);
        }}
        plan={selectedPlan}
        onPaymentComplete={handlePaymentComplete}
      />
    </div>
    </EntitlementsProvider>
  );
}
