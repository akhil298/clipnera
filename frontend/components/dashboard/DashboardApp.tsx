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
import { VideoProject, ViralClip, TabType, UserProfile, Workspace, BrandKit, AppNotification } from '@/lib/types';
import {
  SAMPLE_PROJECTS,
  BRAND_KITS_MOCK,
  NOTIFICATIONS_MOCK,
} from '@/lib/data/mockProjects';
import { userApi, workspaceApi, authApi } from '@/lib/api';

export default function DashboardApp() {
  const router = useRouter();

  // Auth gate: only authenticated users may view the dashboard.
  const [isAuthed, setIsAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      router.replace('/');
    } else {
      setIsAuthed(true);
    }
  }, [router]);

  // Navigation State
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  // Sidebar Layout State
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // User, Workspaces & Brand Kits
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeBrandKit, setActiveBrandKit] = useState<BrandKit>(BRAND_KITS_MOCK[0]);

  // Notifications State
  const [notifications, setNotifications] = useState<AppNotification[]>(NOTIFICATIONS_MOCK);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);

  // Auth / Workspace Modal
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  // Projects State
  const [projects, setProjects] = useState<VideoProject[]>(SAMPLE_PROJECTS);
  const [activeProject, setActiveProject] = useState<VideoProject>(SAMPLE_PROJECTS[0]);
  const [selectedClip, setSelectedClip] = useState<ViralClip>(SAMPLE_PROJECTS[0].clips[0]);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);

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
      } catch {
        // keep previous state on failure
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, [isAuthed]);

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
      setActiveProject((prev) => ({ ...prev, folderName: newName, title: newName }));
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
    setActiveProject((prev) => ({
      ...prev,
      clips: prev.clips.map((c) => (c.id === updatedClip.id ? updatedClip : c)),
    }));
    setProjects((prev) =>
      prev.map((p) =>
        p.id === activeProject.id
          ? { ...p, clips: p.clips.map((c) => (c.id === updatedClip.id ? updatedClip : c)) }
          : p
      )
    );
  };

  // Switch active workspace
  const handleSelectWorkspace = (workspaceId: string) => {
    setCurrentUser((prev) => prev ? { ...prev, activeWorkspaceId: workspaceId } : prev);
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
        />

        {/* Main View Area */}
        <main className="flex-1 min-h-0 w-full p-4 sm:p-6 lg:p-8">
          {/* TAB 1: DASHBOARD HOME */}
          {activeTab === 'dashboard' && (
            <DashboardHomeView
              user={currentUser}
              activeProject={activeProject}
              projects={projects}
              activeBrandKit={activeBrandKit}
              onOpenUpload={() => setIsUploadOpen(true)}
              onSelectProject={handleSelectProject}
              onSelectClipForEdit={handleSelectClipForEdit}
              onScheduleClip={handleScheduleClip}
              onNavigateTab={setActiveTab}
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
            />
          )}

          {/* TAB 3: AI CLIPS GENERATOR / FOLDER DETAIL VIEW */}
          {activeTab === 'generator' && (
            <ClipGeneratorView
              project={activeProject || projects[0] || SAMPLE_PROJECTS[0]}
              onSelectClipForEdit={handleSelectClipForEdit}
              onScheduleClip={handleScheduleClip}
              onOpenUpload={() => setIsUploadOpen(true)}
              onRenameFolder={handleRenameFolder}
              onNavigateTab={setActiveTab}
            />
          )}

          {/* TAB 4: FULL VIDEO EDITOR STUDIO */}
          {activeTab === 'editor' && (
            <VideoEditorStudio
              clip={selectedClip || activeProject?.clips?.[0] || projects[0]?.clips?.[0] || SAMPLE_PROJECTS[0].clips[0]}
              onUpdateClip={handleUpdateClip}
              onBackToGenerator={() => setActiveTab('generator')}
              onScheduleClip={handleScheduleClip}
            />
          )}

          {/* TAB 5: POST TIMING & AI SCHEDULER */}
          {activeTab === 'scheduler' && (
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
    </div>
  );
}
