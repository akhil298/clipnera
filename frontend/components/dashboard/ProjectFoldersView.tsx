"use client";
import React, { useState } from 'react';
import {
  Folder,
  FolderPlus,
  FolderOpen,
  Youtube,
  Sparkles,
  Search,
  Filter,
  Film,
  Flame,
  Clock,
  ArrowRight,
  ExternalLink,
  MoreVertical,
  Download,
  Edit2,
  Trash2,
  CheckCircle2,
  Calendar,
  Layers,
  Plus,
  Scissors,
  Share2,
  Square,
  Zap
} from 'lucide-react';
import { VideoProject, ViralClip } from '@/lib/types';
import { analyzeVideoSource } from '@/lib/utils/urlParser';
import { exportAllProjectClips } from '@/lib/utils/clipExport';
import { StatsSkeleton } from '@/components/skeletons';
import confetti from 'canvas-confetti';
import { Select, SelectOption } from '@/components/ui/Select';

type FolderCategory = 'YouTube Ingest' | 'Podcast' | 'Keynote' | 'Webinar' | 'Interview' | 'Masterclass' | 'Upload' | 'AI Story' | 'Custom';

const FOLDER_CATEGORY_OPTIONS: SelectOption<FolderCategory>[] = [
  { value: 'YouTube Ingest', label: 'YouTube Ingest' },
  { value: 'Podcast', label: 'Podcast' },
  { value: 'Keynote', label: 'Keynote Speech' },
  { value: 'Webinar', label: 'Webinar' },
  { value: 'Interview', label: 'Interview' },
  { value: 'Masterclass', label: 'Masterclass' },
  { value: 'Upload', label: 'Custom Upload' },
];

interface ProjectFoldersViewProps {
  projects: VideoProject[];
  isLoading?: boolean;
  activeProject?: VideoProject;
  onSelectProject: (project: VideoProject) => void;
  onOpenFolder: (project: VideoProject) => void;
  onCreateFolder: (newProject: VideoProject) => void;
  onRenameFolder: (projectId: string, newName: string) => void;
  onDeleteFolder: (projectId: string) => void;
  onOpenUploadModal: () => void;
  onCancelPipeline?: (projectId: string) => void;
}

export const ProjectFoldersView: React.FC<ProjectFoldersViewProps> = ({
  projects,
  isLoading = false,
  activeProject,
  onSelectProject,
  onOpenFolder,
  onCreateFolder,
  onRenameFolder,
  onDeleteFolder,
  onOpenUploadModal,
  onCancelPipeline,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [isNewFolderModalOpen, setIsNewFolderModalOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderCategory, setNewFolderCategory] = useState<FolderCategory>('YouTube Ingest');
  const [exportingProjectId, setExportingProjectId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<{ projectId: string; message: string } | null>(null);
  const [newFolderColor, setNewFolderColor] = useState<'amber' | 'sky' | 'emerald' | 'rose' | 'purple' | 'indigo'>('amber');

  const handleCreateCustomFolder = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;

    const newProjectId = `proj-custom-${Date.now()}`;
    const meta = analyzeVideoSource(newFolderName);

    const newProj: VideoProject = {
      id: newProjectId,
      title: newFolderName,
      folderName: newFolderName,
      folderCategory: newFolderCategory,
      folderColor: newFolderColor,
      sourceUrl: '',
      sourceChannel: 'Custom Workspace',
      description: `Project folder for ${newFolderName}. Ready for video uploads & repurposing.`,
      tags: ['Custom', 'Repurposing', 'Clips'],
      genre: newFolderCategory,
      duration: 600,
      sourceType: 'youtube_url',
      videoUrl: '',
      posterUrl: '',
      uploadedAt: new Date().toISOString(),
      syncStatus: 'synced',
      offlineAvailable: true,
      clips: [],
      transcript: [],
    };

    onCreateFolder(newProj);
    setIsNewFolderModalOpen(false);
    setNewFolderName('');
    confetti({ particleCount: 70, spread: 50 });
    onOpenFolder(newProj);
  };

  const handleDownloadAll = async (project: VideoProject) => {
    setExportError(null);
    setExportingProjectId(project.id);
    try {
      await exportAllProjectClips(project);
      confetti({ particleCount: 60, spread: 50 });
    } catch (error) {
      setExportError({
        projectId: project.id,
        message: error instanceof Error ? error.message : 'Export failed. Please try again.',
      });
    } finally {
      setExportingProjectId(null);
    }
  };

  const handleSaveRename = (projectId: string) => {
    if (renameValue.trim()) {
      onRenameFolder(projectId, renameValue.trim());
    }
    setRenamingProjectId(null);
  };

  // Filter projects/folders
  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      (p.folderName || p.title).toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.sourceChannel || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.tags || []).some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCategory =
      categoryFilter === 'all' ||
      (p.folderCategory || '').toLowerCase() === categoryFilter.toLowerCase() ||
      p.genre.toLowerCase().includes(categoryFilter.toLowerCase());

    return matchesSearch && matchesCategory;
  });

  // Processing cards are 16:9 while completed ones are tall, so each gets its own grid
  const projectSections = [
    { key: 'processing', label: 'Processing', items: filteredProjects.filter((p) => p.processingStatus === 'processing') },
    { key: 'completed', label: 'Completed', items: filteredProjects.filter((p) => p.processingStatus !== 'processing') },
  ].filter((section) => section.items.length > 0);

  // Calculate folder stats
  const totalClips = projects.reduce((acc, p) => acc + (p.clips?.length || 0), 0);
  const avgVirality = Math.round(
    projects.flatMap((p) => p.clips || []).reduce((acc, c) => acc + (c?.viralityScore || 0), 0) /
      (totalClips || 1)
  );

  const getFolderColorClass = (color?: string) => {
    switch (color) {
      case 'sky':
        return 'text-sky-400 bg-sky-500/10 border-sky-500/30';
      case 'emerald':
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
      case 'rose':
        return 'text-rose-400 bg-rose-500/10 border-rose-500/30';
      case 'purple':
        return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
      case 'indigo':
        return 'text-indigo-400 bg-indigo-500/10 border-indigo-500/30';
      case 'amber':
      default:
        return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    }
  };

  return (
    <div className="space-y-7 animate-in fade-in duration-300">
      {/* 1. TOP HERO: Project Folders Hub & YouTube Ingestion Bar */}
      <div className="relative overflow-hidden rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 lg:p-7 shadow-xl">
        <div className="absolute top-0 right-0 w-80 h-80 bg-amber-500/5 blur-3xl pointer-events-none" />

        <div className="relative z-10 space-y-5">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-300 border border-amber-500/25 flex items-center gap-1.5">
                  <Folder className="w-3.5 h-3.5 text-amber-400" />
                  <span>Project-Based Organization</span>
                </span>
                <span className="text-xs text-neutral-400">
                  {projects.length} Dedicated Project Folders
                </span>
              </div>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-white tracking-tight">
                Project Folders & <span className="text-amber-400">Video Workspaces</span>
              </h1>
              <p className="text-neutral-300 text-xs sm:text-sm mt-1 max-w-2xl leading-relaxed">
                Paste any YouTube link or upload a long video. Clipnera automatically generates a named project folder containing all respected viral clips, kinetic subtitles, and repurposing assets.
              </p>
            </div>

            <div className="flex items-center gap-2.5 shrink-0">
              <button
                onClick={() => setIsNewFolderModalOpen(true)}
                className="px-4 py-2.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-white font-bold text-xs border border-neutral-700 shadow-sm transition-all flex items-center gap-2 active:scale-95"
              >
                <FolderPlus className="w-4 h-4 text-amber-400" />
                <span>New Project Folder</span>
              </button>

              <button
                onClick={onOpenUploadModal}
                className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>Upload Long Video</span>
              </button>
            </div>
          </div>

        </div>
      </div>

      {/* 2. STATS ROW */}
      {isLoading ? (
        <StatsSkeleton />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
          <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Active Folders</span>
              <Folder className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">{projects.length}</div>
            <p className="text-[11px] text-neutral-400 font-medium">All organized</p>
          </div>

          <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Total Respected Videos</span>
              <Film className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">{totalClips}</div>
            <p className="text-[11px] text-neutral-400 font-medium">Inside folders</p>
          </div>

          <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Avg Folder Virality</span>
              <Flame className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">{avgVirality} / 100</div>
            <p className="text-[11px] text-amber-400 font-medium">Top tier ranking</p>
          </div>

          <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
            <div className="flex items-center justify-between text-neutral-400">
              <span className="text-xs font-medium">Original Watchtime</span>
              <Clock className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">
              {Math.round(projects.reduce((acc, p) => acc + (p.duration || 0), 0) / 60)} mins
            </div>
            <p className="text-[11px] text-neutral-400 font-medium">Repurposed into shorts</p>
          </div>
        </div>
      )}

      {/* 3. SEARCH & FILTER TOOLBAR */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
          <input
            type="text"
            placeholder="Search folders by title, channel, or tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-neutral-900 border border-neutral-800 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors"
          />
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {[
            { id: 'all', label: 'All Folders' },
            { id: 'youtube ingest', label: 'YouTube Ingests' },
            { id: 'ai story', label: 'AI Prompt Stories' },
            { id: 'upload', label: 'Uploads' },
            { id: 'podcast', label: 'Podcasts' },
            { id: 'keynote', label: 'Keynotes' },
            { id: 'masterclass', label: 'Masterclasses' },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                categoryFilter === cat.id
                  ? 'bg-amber-500 text-neutral-950 font-bold'
                  : 'bg-neutral-900 hover:bg-neutral-800 text-neutral-400 hover:text-neutral-200 border border-neutral-800'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* 4. FOLDERS GRID */}
      {filteredProjects.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-neutral-900/40 border border-neutral-800/80 space-y-4">
          <Folder className="w-12 h-12 text-neutral-600 mx-auto" />
          <h3 className="text-base font-bold text-white">No Project Folders Found</h3>
          <p className="text-xs text-neutral-400 max-w-sm mx-auto">
            Try adjusting your search filters, paste a YouTube link above, or create a brand new project folder.
          </p>
          <button
            onClick={() => {
              setSearchQuery('');
              setCategoryFilter('all');
            }}
            className="px-4 py-2 rounded-lg bg-neutral-800 text-xs text-amber-400 font-semibold hover:bg-neutral-700"
          >
            Clear Filters
          </button>
        </div>
      ) : (
        projectSections.map((section) => (
        <section key={section.key} className="space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-400">
            {section.label} <span className="font-mono text-neutral-500">({section.items.length})</span>
          </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {section.items.map((project) => {
            const isSelected = project.id === activeProject?.id;
            const displayName = project.folderName || project.title;
            const isEditing = renamingProjectId === project.id;
            const colorClass = getFolderColorClass(project.folderColor);
            const progress = project.processingProgress ?? 0;

            return (
          <div
            key={project.id}
            className={`group rounded-2xl border transition-all flex flex-col justify-between overflow-hidden shadow-lg relative ${
              isSelected
                ? 'bg-neutral-900 border-amber-500/60 ring-1 ring-amber-500/30'
                : project.processingStatus === 'processing'
                  ? 'bg-neutral-900 border-neutral-800 hover:border-neutral-700'
                  : 'bg-neutral-900/80 border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900'
            } ${(project.processingStatus === 'processing') ? 'ring-1 ring-amber-500/40 aspect-video self-start' : ''}`}
          >
            {/* Thumbnail background during processing */}
            {project.processingStatus === 'processing' && project.posterUrl && (
              <div
                className="absolute inset-0 bg-cover bg-center pointer-events-none"
                style={{ backgroundImage: `url(${project.posterUrl})` }}
              />
            )}

            {/* Loading overlay: the loaded part (left) lightens toward the
                progress edge, the part still to load (right) stays dark */}
            {project.processingStatus === 'processing' && (
              <>
                <div
                  className="absolute inset-y-0 left-0 bg-gradient-to-r from-black/60 to-black/20 pointer-events-none transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                />
                <div
                  className="absolute inset-y-0 right-0 bg-black/80 pointer-events-none transition-all duration-500 ease-out"
                  style={{ left: `${progress}%` }}
                />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-amber-400 shadow-lg animate-pulse z-10"
                  style={{ left: `calc(${progress}% - 8px)` }}
                />
              </>
            )}

            {/* Credits Charged Badge */}
            {project.creditsDeducted && project.creditsDeducted > 0 && (
              <div className="absolute top-2 right-2 z-10 flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20">
                <Zap className="w-3 h-3 text-amber-400" />
                <span className="text-[9px] font-mono font-semibold text-amber-300">
                  {project.creditsDeducted} credit{project.creditsDeducted !== 1 ? 's' : ''}
                </span>
              </div>
            )}

            {/* Processing Progress Bar */}
          {project.processingStatus === 'processing' && (
            <div className="w-full h-1 bg-neutral-800">
              <div
                className="h-full bg-amber-500 transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}

          {/* Folder Top Tab Header */}
                <div className="p-4 pb-3 border-b border-neutral-800/80">
                  <div className="flex items-start justify-between gap-2">
                    {/* Folder Icon & Category */}
                    <div className="flex items-center gap-2.5">
                      <div className={`p-2.5 rounded-xl border ${colorClass} shadow-sm`}>
                        <Folder className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 block">
                          {project.folderCategory || project.genre}
                        </span>
                        {project.sourceChannel && (
                          <span className="text-[11px] font-semibold text-neutral-300 line-clamp-1">
                            {project.sourceChannel}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Source Badge & Link */}
                    <div className="flex items-center gap-1.5">
                      {project.processingStatus === 'processing' && (
                        <span className="px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-[10px] font-semibold text-amber-300 flex items-center gap-1 animate-pulse">
                          <Sparkles className="w-3 h-3 text-amber-400" />
                          <span>Processing {progress}%</span>
                        </span>
                      )}
                      {/* Reachable without scrolling to the footer while a run is live */}
                      {project.processingStatus === 'processing' && (
                        <div className="relative z-10 flex items-center gap-1">
                          {onCancelPipeline && (
                            <button
                              onClick={() => onCancelPipeline(project.id)}
                              className="p-1.5 rounded-lg bg-black/60 border border-neutral-700 text-neutral-300 hover:text-amber-300 hover:border-amber-500/40 transition-colors"
                              title="Stop processing"
                              aria-label="Stop processing"
                            >
                              <Square className="w-3 h-3 fill-current" />
                            </button>
                          )}
                          <button
                            onClick={() => onDeleteFolder(project.id)}
                            className="p-1.5 rounded-lg bg-black/60 border border-neutral-700 text-neutral-300 hover:text-rose-400 hover:border-rose-500/40 transition-colors"
                            title="Stop and delete project"
                            aria-label="Stop and delete project"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                      {project.processingStatus === 'failed' && (
                        <span className="px-2 py-0.5 rounded-md bg-rose-500/10 border border-rose-500/20 text-[10px] font-semibold text-rose-300 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                          <span>Failed</span>
                        </span>
                      )}

                      {project.sourceType === 'youtube_url' && !project.processingStatus && (
                        <span className="px-2 py-0.5 rounded-md bg-rose-500/10 border border-rose-500/20 text-[10px] font-semibold text-rose-300 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                          <span>YouTube</span>
                        </span>
                      )}

                      {project.audioEnhancement?.aiDenoise && (
                        <span className="px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-[10px] font-semibold text-amber-300 flex items-center gap-1" title="AI Background Noise Removed">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          <span>Denoised</span>
                        </span>
                      )}

                      {project.sourceUrl && (
                        <a
                          href={project.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2 py-1 rounded-md bg-neutral-950 border border-neutral-800 text-[10px] font-medium text-neutral-400 hover:text-amber-400 hover:border-neutral-700 flex items-center gap-1 transition-colors"
                          title="Open Source Video"
                        >
                          <Youtube className="w-3 h-3 text-red-400" />
                          <span>Source</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Folder Title (Editable) */}
                  <div className="mt-3">
                    {isEditing ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="text"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          className="flex-1 px-2.5 py-1 rounded bg-neutral-950 border border-amber-400 text-xs text-white focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveRename(project.id)}
                          className="px-2.5 py-1 rounded bg-amber-500 text-neutral-950 text-xs font-bold"
                        >
                          Save
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between group/title">
                        <h3 className="text-sm font-bold text-white line-clamp-2 leading-snug">
                          {displayName}
                        </h3>
                        <button
                          onClick={() => {
                            setRenamingProjectId(project.id);
                            setRenameValue(displayName);
                          }}
                          className="opacity-0 group-hover/title:opacity-100 p-1 hover:text-amber-400 text-neutral-400 transition-opacity ml-1 shrink-0"
                          title="Rename Folder"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                      </div>
                    )}

                    <p className="text-[11px] text-neutral-400 mt-1 line-clamp-2 leading-relaxed">
                      {project.description || 'AI analysis completed. Clips generated with kinetic captions.'}
                    </p>
                  </div>
                </div>

                {/* Folder Body: Mini Thumbnails of Respected Videos Inside */}
                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between text-[11px] text-neutral-400">
                    <span className="font-semibold text-neutral-300 flex items-center gap-1">
                      <Film className="w-3.5 h-3.5 text-amber-400" />
                      <span>{project.clips.length} Respected Videos Inside:</span>
                    </span>
                    <span className="font-mono text-neutral-400">
                      {Math.floor(project.duration / 60)}m {project.duration % 60}s raw
                    </span>
                  </div>

                  {/* Visual Clips Preview Strip */}
                  <div className="grid grid-cols-3 gap-2">
                    {project.clips.slice(0, 3).map((clip) => (
                      <div
                        key={clip.id}
                        onClick={() => {
                          if (project.processingStatus === 'processing') return;
                          onSelectProject(project);
                          onOpenFolder(project);
                        }}
                        className={`group/clip relative aspect-[9/14] rounded-lg bg-neutral-950 overflow-hidden border border-neutral-800/80 transition-all shadow-sm ${
                          project.processingStatus === 'processing'
                            ? 'opacity-50 cursor-not-allowed'
                            : 'cursor-pointer hover:border-amber-400/60'
                        }`}
                      >
                        {/* The clip's own frame only — never the project thumbnail,
                            which would show the same image for every clip. */}
                        {clip.posterUrl ? (
                          <img
                            src={clip.posterUrl}
                            alt={clip.title}
                            className="w-full h-full object-cover group-hover/clip:scale-105 transition-transform duration-300"
                          />
                        ) : (
                          <div className="w-full h-full bg-neutral-800 flex items-center justify-center">
                            <span className="text-neutral-500 text-xs">No preview</span>
                          </div>
                        )}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/20" />
                        
                        {/* Virality badge */}
                        <div className="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-black/80 text-[9px] font-mono font-bold text-amber-300 border border-amber-500/30">
                          {clip.viralityScore}
                        </div>

                        {/* Duration */}
                        <div className="absolute bottom-1 right-1 text-[8px] font-mono text-neutral-300 px-1 rounded bg-black/70">
                          {clip.duration}s
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Tags */}
                  {project.tags && project.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {project.tags.slice(0, 3).map((tag, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded text-[10px] bg-neutral-950 border border-neutral-800 text-neutral-400 font-medium"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Folder Footer & Open Action */}
                <div className="mt-auto p-3.5 bg-neutral-950/60 border-t border-neutral-800/80 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5 min-w-0">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold whitespace-nowrap bg-amber-500/10 text-amber-300 border border-amber-500/20">
                      {project.processingStatus === 'processing'
                        ? `Processing ${progress}%`
                        : `Avg ${Math.round(project.clips.reduce((acc, c) => acc + c.viralityScore, 0) / (project.clips.length || 1))}/100`}
                    </span>
                    {project.processingStatus === 'processing' && onCancelPipeline && (
                      <button
                        onClick={() => onCancelPipeline(project.id)}
                        className="px-2 py-0.5 rounded text-[10px] font-semibold text-rose-300 border border-rose-500/30 hover:bg-rose-500/10"
                      >
                        Cancel
                      </button>
                    )}
                    {isSelected && project.processingStatus !== 'processing' && (
                      <span className="text-[10px] text-emerald-400 font-bold whitespace-nowrap flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Active
                      </span>
                    )}
                  </div>

                  <div className="ml-auto flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => handleDownloadAll(project)}
                      disabled={project.processingStatus === 'processing' || exportingProjectId === project.id || project.clips.length === 0}
                      className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-neutral-800 disabled:hover:text-neutral-300"
                      title={exportingProjectId === project.id ? 'Preparing downloads…' : 'Download all videos in this folder'}
                      aria-label="Download all videos in this folder"
                    >
                      {exportingProjectId === project.id ? (
                        <Sparkles className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Download className="w-3.5 h-3.5" />
                      )}
                    </button>

                    <button
                      onClick={() => {
                        if (project.processingStatus === 'processing') return;
                        onSelectProject(project);
                        onOpenFolder(project);
                      }}
                      disabled={project.processingStatus === 'processing'}
                      className={`px-3.5 py-1.5 rounded-lg font-bold text-xs whitespace-nowrap transition-all flex items-center gap-1.5 shadow-sm active:scale-95 ${
                        project.processingStatus === 'processing'
                          ? 'bg-neutral-700 text-neutral-500 cursor-not-allowed'
                          : 'bg-amber-500 hover:bg-amber-400 text-neutral-950'
                      }`}
                    >
                      {project.processingStatus === 'processing' ? (
                        <>
                          <Sparkles className="w-3.5 h-3.5 animate-spin" />
                          <span>Processing...</span>
                        </>
                      ) : (
                        <>
                          <FolderOpen className="w-3.5 h-3.5" />
                          <span>Open Folder</span>
                          <ArrowRight className="w-3 h-3" />
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => {
                        onDeleteFolder(project.id);
                      }}
                      className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                      title="Delete Project"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {exportError?.projectId === project.id && (
                    <p role="alert" className="basis-full text-[11px] text-rose-300">
                      {exportError.message}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        </section>
        ))
      )}

      {/* 5. NEW FOLDER MODAL */}
      {isNewFolderModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg rounded-2xl bg-neutral-900 border border-neutral-800 p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/30">
                  <FolderPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Create New Project Folder</h3>
                  <p className="text-xs text-neutral-400">Organize clips by show, topic, or YouTube series</p>
                </div>
              </div>
              <button
                onClick={() => setIsNewFolderModalOpen(false)}
                className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCustomFolder} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-neutral-300 block mb-1.5">
                  Folder / Project Name:
                </label>
                <input
                  type="text"
                  placeholder="e.g. Alex Hormozi — $100M Leads Masterclass"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-neutral-300 block mb-1.5">
                    Category:
                  </label>
                  <Select
                    value={newFolderCategory}
                    onChange={setNewFolderCategory}
                    options={FOLDER_CATEGORY_OPTIONS}
                    className="w-full px-3 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700 text-xs text-white focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-neutral-300 block mb-1.5">
                    Folder Theme Color:
                  </label>
                  <div className="flex items-center gap-2 pt-1">
                    {(['amber', 'sky', 'emerald', 'rose', 'purple', 'indigo'] as const).map((color) => (
                      <button
                        key={color}
                        type="button"
                        onClick={() => setNewFolderColor(color)}
                        className={`w-6 h-6 rounded-full border-2 transition-all ${
                          newFolderColor === color ? 'border-white scale-110' : 'border-transparent opacity-70'
                        } ${
                          color === 'amber'
                            ? 'bg-amber-400'
                            : color === 'sky'
                            ? 'bg-sky-400'
                            : color === 'emerald'
                            ? 'bg-emerald-400'
                            : color === 'rose'
                            ? 'bg-rose-400'
                            : color === 'purple'
                            ? 'bg-purple-400'
                            : 'bg-indigo-400'
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-neutral-800 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setIsNewFolderModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-neutral-800 text-xs font-medium text-neutral-300 hover:bg-neutral-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!newFolderName.trim()}
                  className="px-5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/15"
                >
                  Create & Open Folder
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
