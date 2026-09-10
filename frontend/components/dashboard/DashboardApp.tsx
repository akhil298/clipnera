"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
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
import { SettingsView } from './SettingsView';
import { NotificationsDrawer } from './NotificationsDrawer';
import { AuthModal } from './AuthModal';
import { PlanSelectionModal } from './PlanSelectionModal';
import { PaymentModal } from './PaymentModal';
import { VideoProject, ViralClip, TabType, UserProfile, Workspace, AppNotification, PipelineStep } from '@/lib/types';
import { userApi, workspaceApi, authApi, pipelineApi, subscriptionApi } from '@/lib/api';
import { isAuthenticated, clearAuth } from '@/lib/auth';

export default function DashboardApp() {
  const router = useRouter();

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
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [activeSettingsTab, setActiveSettingsTab] = useState<'account' | 'billing' | 'social' | 'team'>('account');

  // Sidebar Layout State
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // User, Workspaces & Notifications
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);

  // Notifications State
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);

  // Auth / Workspace Modal
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  // Projects State
  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [activeProject, setActiveProject] = useState<VideoProject | undefined>(undefined);
  const [selectedClip, setSelectedClip] = useState<ViralClip | undefined>(undefined);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [isAudioReverted, setIsAudioReverted] = useState(false);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Plan & Payment modals state
  const [isPlanModalOpen, setIsPlanModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<{ id: string; name: string; slug: string; credit_minutes: number; price_monthly: number; currency: string } | null>(null);

  // Fetch real user profile and workspaces on mount
  useEffect(() => {
    if (!isAuthed) return;
    let cancelled = false;

    async function loadData() {
      try {
        const [profile, wsList] = await Promise.all([
          userApi.getMe(),
          workspaceApi.list(),
        ]);
        if (cancelled) return;
        const mappedUser: UserProfile = {
          id: profile.id,
          name: profile.name,
          email: profile.email,
          avatarUrl: profile.avatar_url || '',
          avatarInitials: profile.avatar_initials,
          plan: profile.plan as UserProfile['plan'],
          aiCreditsMinutesRemaining: profile.ai_credits_minutes_remaining,
          aiCreditsTotal: profile.ai_credits_total,
          activeWorkspaceId: profile.active_workspace_id || wsList[0]?.id || '',
          providers: profile.providers,
        };
        setCurrentUser(mappedUser);
        setWorkspaces(
          wsList.map((ws) => ({
            id: ws.id,
            name: ws.name,
            role: ws.role as Workspace['role'],
            membersCount: ws.member_count,
          }))
        );
      } catch (err) {
        if (err instanceof Error && err.message.startsWith('Unauthorized:')) {
          clearAuth();
          router.replace('/');
        }
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, [isAuthed]);

  useEffect(() => {
    if (!activeProject?.id) return;
    let cancelled = false;
    pipelineApi.getStatus(activeProject.id).then((status) => {
      if (!cancelled) {
        setPipelineSteps(status.steps || []);
      }
    }).catch(() => {
      if (!cancelled) {
        setPipelineSteps([]);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [activeProject?.id]);

  const handleRevertPipelineStep = async (step: string) => {
    if (!activeProject?.id) return;
    try {
      await pipelineApi.revertStep(activeProject.id, step);
      const status = await pipelineApi.getStatus(activeProject.id);
      setPipelineSteps(status.steps || []);
    } catch (err) {
      console.error('Failed to revert step:', err);
    }
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
    setNotifications([newNotif, ...notifications]);
    setActiveTab('generator');
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
    setActiveTab('generator');
  };

  // Handle deleting a folder
  const handleDeleteFolder = (projectId: string) => {
    const updated = projects.filter((p) => p.id !== projectId);
    setProjects(updated);
    if (activeProject?.id === projectId) {
      if (updated.length > 0) {
        setActiveProject(updated[0]);
        if (updated[0].clips.length > 0) {
          setSelectedClip(updated[0].clips[0]);
        }
      }
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
    setActiveTab('editor');
  };

  // Handle scheduling a clip
  const handleScheduleClip = (clip: ViralClip) => {
    setSelectedClip(clip);
    setActiveTab('scheduler');
  };

  // Handle selecting a project from dashboard
  const handleSelectProject = (project: VideoProject) => {
    setActiveProject(project);
    if (project.clips.length > 0) {
      setSelectedClip(project.clips[0]);
    }
    setActiveTab('generator');
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
    setActiveTab('settings');
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

  // Notifications helpers
  const unreadCount = notifications.filter((n) => !n.read).length;
  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };
  const handleClearNotifications = () => {
    setNotifications([]);
  };

  const handlePaymentComplete = async () => {
    setIsPaymentModalOpen(false);
    setIsPlanModalOpen(false);
    setSelectedPlan(null);
    let cancelled = false;
    try {
      const profile = await userApi.getMe();
      if (!cancelled) {
        const mappedUser: UserProfile = {
          id: profile.id,
          name: profile.name,
          email: profile.email,
          avatarUrl: profile.avatar_url || '',
          avatarInitials: profile.avatar_initials,
          plan: profile.plan as UserProfile['plan'],
          aiCreditsMinutesRemaining: profile.ai_credits_minutes_remaining,
          aiCreditsTotal: profile.ai_credits_total,
          activeWorkspaceId: profile.active_workspace_id || currentUser?.activeWorkspaceId || '',
          providers: profile.providers,
        };
        setCurrentUser(mappedUser);
      }
    } catch {
      // ignore
    }
    return () => { cancelled = true; };
  };

  const handleActivateFree = async () => {
    setIsPlanModalOpen(false);
    let cancelled = false;
    try {
      await subscriptionApi.activateFreePlan();
      if (!cancelled) {
        await handlePaymentComplete();
      }
    } catch {
      // ignore
    }
    return () => { cancelled = true; };
  };

  const handlePlanSelected = (plan: { id: string; name: string; slug: string; credit_minutes: number; price_monthly: number; currency: string }) => {
    setSelectedPlan(plan);
    setIsPaymentModalOpen(true);
  };



  if (isAuthed === null || !currentUser) {
    return (
      <div className="min-h-screen bg-neutral-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex font-['Plus_Jakarta_Sans',sans-serif]">
      {/* Left Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenUpload={() => setIsUploadOpen(true)}
        user={currentUser}
        workspaces={workspaces}
        projects={projects}
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
        onNavigateTab={setActiveTab}
        onUpgradePlan={navigateToBilling}
      />

        {/* Main View Area */}
        <main className="flex-1 min-h-0 w-full p-4 sm:p-6 lg:p-8">
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
              onNavigateTab={setActiveTab}
              onUpgradePlan={navigateToBilling}
            />
          )}

          {/* TAB 2: PROJECT FOLDERS HUB */}
          {activeTab === 'folders' && (
            <ProjectFoldersView
              projects={projects}
              activeProject={activeProject}
              onOpenFolder={handleOpenFolder}
              onSelectProject={handleOpenFolder}
              onCreateFolder={handleProjectCreated}
              onDeleteFolder={handleDeleteFolder}
              onRenameFolder={handleRenameFolder}
              onOpenUploadModal={() => setIsUploadOpen(true)}
              onUpdateProject={handleUpdateProject}
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
              onNavigateTab={setActiveTab}
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
              onBackToGenerator={() => setActiveTab('generator')}
              onScheduleClip={handleScheduleClip}
            />
          )}

          {/* TAB 5: POST TIMING & AI SCHEDULER (HIDDEN — preserved for later) */}
          {false && activeTab === 'scheduler' && (
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
        isOpen={isPlanModalOpen}
        onClose={() => {
          setIsPlanModalOpen(false);
          setSelectedPlan(null);
        }}
        onPlanSelected={handlePlanSelected}
        onActivateFree={handleActivateFree}
      />

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
  );
}
