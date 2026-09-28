"use client";
import React, { useEffect, useState } from 'react';
import {
  ArrowRight,
  Check,
  Download,
  Edit2,
  ExternalLink,
  Film,
  FolderPlus,
  LayoutGrid,
  List,
  Loader2,
  Plus,
  Search,
  Square,
  Trash2,
  X,
  Zap,
} from 'lucide-react';
import { VideoProject } from '@/lib/types';
import { exportAllProjectClips } from '@/lib/utils/clipExport';
import { formatRelativeTime } from '@/lib/utils/dates';
import { StatsSkeleton } from '@/components/skeletons';
import confetti from 'canvas-confetti';
import { Select, SelectOption } from '@/components/ui/Select';
import { PageHeader } from '@/components/ui/PageHeader';
import { StatusPill, projectStatus } from '@/components/ui/StatusPill';
import { NotWiredBadge } from '@/components/ui/NotWiredBadge';

type FolderCategory = 'YouTube Ingest' | 'Podcast' | 'Keynote' | 'Webinar' | 'Interview' | 'Masterclass' | 'Upload' | 'AI Story' | 'Custom';
type FolderColor = NonNullable<VideoProject['folderColor']>;
type StatusFilter = 'all' | 'processing' | 'ready' | 'failed';
type ViewMode = 'grid' | 'list';

const FOLDER_CATEGORY_OPTIONS: SelectOption<FolderCategory>[] = [
  { value: 'YouTube Ingest', label: 'YouTube Ingest' },
  { value: 'Podcast', label: 'Podcast' },
  { value: 'Keynote', label: 'Keynote Speech' },
  { value: 'Webinar', label: 'Webinar' },
  { value: 'Interview', label: 'Interview' },
  { value: 'Masterclass', label: 'Masterclass' },
  { value: 'Upload', label: 'Custom Upload' },
];

/** Source filters the backend can answer (every project is a YouTube ingest or an upload). */
const SOURCE_FILTERS = [
  { id: 'all', label: 'All sources' },
  { id: 'youtube ingest', label: 'YouTube' },
  { id: 'upload', label: 'Uploads' },
];

/** Topic filters shown today that no project can match yet: the backend stores no topic. */
const TOPIC_FILTERS = [
  { id: 'podcast', label: 'Podcasts' },
  { id: 'keynote', label: 'Keynotes' },
  { id: 'masterclass', label: 'Masterclasses' },
  { id: 'ai story', label: 'AI prompt stories' },
];

const FOLDER_COLORS: Record<FolderColor, string> = {
  amber: 'bg-amber-400',
  sky: 'bg-sky-400',
  emerald: 'bg-emerald-400',
  rose: 'bg-rose-400',
  purple: 'bg-purple-400',
  indigo: 'bg-indigo-400',
};

const VIEW_MODE_KEY = 'clipnera.projectsView';

const formatMinutes = (seconds: number) => {
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return minutes > 0 ? `${minutes}:${String(rest).padStart(2, '0')}` : `0:${String(rest).padStart(2, '0')}`;
};

const projectThumb = (project: VideoProject) => project.posterUrl || project.clips.find((c) => c.posterUrl)?.posterUrl || '';

const matchesStatus = (project: VideoProject, filter: StatusFilter) => {
  if (filter === 'all') return true;
  if (filter === 'processing') return project.processingStatus === 'processing';
  if (filter === 'failed') return project.processingStatus === 'failed';
  return project.processingStatus !== 'processing' && project.processingStatus !== 'failed';
};

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
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [isNewFolderModalOpen, setIsNewFolderModalOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderCategory, setNewFolderCategory] = useState<FolderCategory>('YouTube Ingest');
  const [exportingProjectId, setExportingProjectId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<{ projectId: string; message: string } | null>(null);
  const [newFolderColor, setNewFolderColor] = useState<FolderColor>('amber');

  useEffect(() => {
    try {
      const saved = localStorage.getItem(VIEW_MODE_KEY);
      if (saved === 'grid' || saved === 'list') setViewMode(saved);
    } catch {
      // Storage can be unavailable; the grid is a fine default.
    }
  }, []);

  const changeViewMode = (mode: ViewMode) => {
    setViewMode(mode);
    try {
      localStorage.setItem(VIEW_MODE_KEY, mode);
    } catch {
      // Remembering the choice is a convenience only.
    }
  };

  const handleCreateCustomFolder = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;

    const newProjectId = `proj-custom-${Date.now()}`;

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

  const openProject = (project: VideoProject) => {
    if (project.processingStatus === 'processing') return;
    onSelectProject(project);
    onOpenFolder(project);
  };

  const query = searchQuery.toLowerCase();
  const searchedProjects = projects.filter((p) => {
    const matchesSearch =
      (p.folderName || p.title).toLowerCase().includes(query) ||
      (p.sourceChannel || '').toLowerCase().includes(query) ||
      (p.tags || []).some((t) => t.toLowerCase().includes(query));
    const matchesCategory =
      categoryFilter === 'all' ||
      (p.folderCategory || '').toLowerCase() === categoryFilter.toLowerCase() ||
      p.genre.toLowerCase().includes(categoryFilter.toLowerCase());
    return matchesSearch && matchesCategory;
  });
  const filteredProjects = searchedProjects.filter((p) => matchesStatus(p, statusFilter));
  const statusCounts: Record<StatusFilter, number> = {
    all: searchedProjects.length,
    processing: searchedProjects.filter((p) => matchesStatus(p, 'processing')).length,
    ready: searchedProjects.filter((p) => matchesStatus(p, 'ready')).length,
    failed: searchedProjects.filter((p) => matchesStatus(p, 'failed')).length,
  };

  const totalClips = projects.reduce((acc, p) => acc + (p.clips?.length || 0), 0);
  const avgVirality = Math.round(
    projects.flatMap((p) => p.clips || []).reduce((acc, c) => acc + (c?.viralityScore || 0), 0) / (totalClips || 1),
  );
  const sourceMinutes = Math.round(projects.reduce((acc, p) => acc + (p.duration || 0), 0) / 60);
  const hasFilters = searchQuery !== '' || categoryFilter !== 'all' || statusFilter !== 'all';

  const clearFilters = () => {
    setSearchQuery('');
    setCategoryFilter('all');
    setStatusFilter('all');
  };

  const chip = (id: string, label: string) => (
    <button
      key={id}
      type="button"
      onClick={() => setCategoryFilter(id)}
      aria-pressed={categoryFilter === id}
      className={`h-7 px-2.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors ${
        categoryFilter === id
          ? 'bg-amber-500 text-neutral-950'
          : 'bg-neutral-900 text-neutral-400 hover:text-neutral-200 border border-neutral-800'
      }`}
    >
      {label}
    </button>
  );

  const renameField = (project: VideoProject) => (
    <form
      className="flex items-center gap-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        handleSaveRename(project.id);
      }}
    >
      <label htmlFor={`rename-${project.id}`} className="sr-only">
        Project name
      </label>
      <input
        id={`rename-${project.id}`}
        type="text"
        value={renameValue}
        onChange={(e) => setRenameValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && setRenamingProjectId(null)}
        className="flex-1 min-w-0 h-8 px-2.5 rounded-lg bg-neutral-950 border border-amber-400 text-sm text-white focus:outline-none"
        autoFocus
      />
      <button type="submit" className="h-8 px-2.5 rounded-lg bg-amber-500 text-neutral-950 text-xs font-bold">
        Save
      </button>
      <button
        type="button"
        onClick={() => setRenamingProjectId(null)}
        className="h-8 w-8 flex items-center justify-center rounded-lg text-neutral-400 hover:text-white"
        aria-label="Cancel rename"
      >
        <X className="w-4 h-4" />
      </button>
    </form>
  );

  const renameButton = (project: VideoProject, displayName: string) => (
    <button
      type="button"
      onClick={() => {
        setRenamingProjectId(project.id);
        setRenameValue(displayName);
      }}
      className="p-1 rounded-md text-neutral-500 hover:text-amber-400 sm:opacity-0 sm:group-hover:opacity-100 focus-visible:opacity-100 transition-opacity shrink-0"
      title="Rename project"
      aria-label={`Rename ${displayName}`}
    >
      <Edit2 className="w-3.5 h-3.5" />
    </button>
  );

  const downloadButton = (project: VideoProject) => (
    <button
      type="button"
      onClick={() => handleDownloadAll(project)}
      disabled={project.processingStatus === 'processing' || exportingProjectId === project.id || project.clips.length === 0}
      className="h-8 w-8 flex items-center justify-center rounded-lg border border-neutral-800 text-neutral-300 hover:text-white hover:bg-neutral-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
      title={exportingProjectId === project.id ? 'Preparing downloads…' : 'Download all clips'}
      aria-label="Download all clips in this project"
    >
      {exportingProjectId === project.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
    </button>
  );

  const deleteButton = (project: VideoProject) => (
    <button
      type="button"
      onClick={() => onDeleteFolder(project.id)}
      className="h-8 w-8 flex items-center justify-center rounded-lg border border-neutral-800 text-neutral-400 hover:text-rose-300 hover:border-rose-500/40 hover:bg-rose-500/5 transition-colors"
      title={project.processingStatus === 'processing' ? 'Stop and delete project' : 'Delete project'}
      aria-label={project.processingStatus === 'processing' ? 'Stop and delete project' : 'Delete project'}
    >
      <Trash2 className="w-3.5 h-3.5" />
    </button>
  );

  const renderCard = (project: VideoProject) => {
    const isSelected = project.id === activeProject?.id;
    const displayName = project.folderName || project.title;
    const isEditing = renamingProjectId === project.id;
    const isProcessing = project.processingStatus === 'processing';
    const isFailed = project.processingStatus === 'failed';
    const progress = Math.round(project.processingProgress ?? 0);
    const status = projectStatus(project);
    const thumb = projectThumb(project);
    const avg = Math.round(project.clips.reduce((acc, c) => acc + c.viralityScore, 0) / (project.clips.length || 1));

    return (
      <article
        key={project.id}
        className={`group rounded-2xl border bg-neutral-900/80 overflow-hidden flex flex-col transition-colors ${
          isSelected ? 'border-amber-500/50 ring-1 ring-amber-500/20' : 'border-neutral-800 hover:border-neutral-700'
        }`}
      >
        {/* Thumbnail */}
        <button
          type="button"
          onClick={() => openProject(project)}
          disabled={isProcessing}
          className="relative aspect-[16/8] bg-neutral-950 overflow-hidden text-left disabled:cursor-default"
          aria-label={isProcessing ? `${displayName} is processing` : `Open ${displayName}`}
        >
          {thumb ? (
            <img
              src={thumb}
              alt=""
              loading="lazy"
              className={`absolute inset-0 w-full h-full object-cover transition-transform duration-500 ${isProcessing ? 'opacity-40' : 'group-hover:scale-[1.03]'}`}
            />
          ) : (
            <span className="absolute inset-0 flex items-center justify-center bg-[radial-gradient(circle_at_30%_20%,rgba(245,158,11,0.12),transparent_60%)]">
              <Film className="w-7 h-7 text-neutral-700" />
            </span>
          )}
          <span className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30" />
          <span className="absolute top-2.5 left-2.5">
            <StatusPill tone={status.tone}>{isProcessing ? `Processing ${progress}%` : status.label}</StatusPill>
          </span>
          {project.duration > 0 && (
            <span className="absolute bottom-2.5 right-2.5 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-white">
              {formatMinutes(project.duration)}
            </span>
          )}
          {isProcessing && (
            <span className="absolute inset-x-0 bottom-0 h-1 bg-neutral-800">
              <span className="block h-full bg-amber-500 transition-all duration-500" style={{ width: `${progress}%` }} />
            </span>
          )}
        </button>

        {/* Body */}
        <div className="p-4 flex-1 flex flex-col gap-3">
          <div className="space-y-1">
            {isEditing ? (
              renameField(project)
            ) : (
              <div className="flex items-start gap-1">
                <h3 className="flex-1 text-sm font-semibold text-white leading-snug line-clamp-2">{displayName}</h3>
                {renameButton(project, displayName)}
              </div>
            )}
            <p className="text-[11.5px] text-neutral-500 truncate">
              {[project.folderCategory === 'Upload' ? 'Upload' : project.sourceChannel || project.folderCategory || project.genre, formatRelativeTime(project.uploadedAt)]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>

          {(project.audioEnhancement?.aiDenoise || (project.creditsDeducted ?? 0) > 0 || project.sourceUrl) && (
            <div className="flex flex-wrap items-center gap-1.5">
              {project.audioEnhancement?.aiDenoise && (
                <StatusPill tone="ready" className="!h-5 !text-[10px]" title="Background noise removed">
                  Denoised
                </StatusPill>
              )}
              {(project.creditsDeducted ?? 0) > 0 && (
                <StatusPill tone="neutral" dot={false} className="!h-5 !text-[10px]">
                  <Zap className="w-3 h-3 text-amber-400" />
                  {project.creditsDeducted} credit{project.creditsDeducted !== 1 ? 's' : ''}
                </StatusPill>
              )}
              {project.sourceUrl && (
                <a
                  href={project.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 h-5 px-1.5 rounded-full border border-neutral-800 text-[10px] font-semibold text-neutral-400 hover:text-amber-300 hover:border-neutral-700"
                >
                  Source <ExternalLink className="w-2.5 h-2.5" />
                </a>
              )}
            </div>
          )}

          {isFailed && (
            <p className="rounded-lg bg-rose-500/10 border border-rose-500/20 px-3 py-2 text-[11.5px] text-rose-200">
              {project.description && project.description !== 'AI analysis completed. Clips generated with kinetic captions.'
                ? project.description
                : 'Processing stopped before clips were ready.'}
            </p>
          )}

          {/* The clips inside */}
          {project.clips.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex -space-x-2">
                {project.clips.slice(0, 4).map((clip) => (
                  <span
                    key={clip.id}
                    className="relative w-7 aspect-[9/13] rounded-md overflow-hidden border-2 border-neutral-900 bg-neutral-800"
                  >
                    {clip.posterUrl && <img src={clip.posterUrl} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover" />}
                  </span>
                ))}
              </div>
              <span className="text-[11.5px] text-neutral-400">
                {project.clips.length} clip{project.clips.length === 1 ? '' : 's'} · average score{' '}
                <span className="font-semibold text-neutral-200 tabular-nums">{avg}</span>
              </span>
            </div>
          )}

          {project.tags && project.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {project.tags.slice(0, 3).map((tag) => (
                <span key={tag} className="px-1.5 py-0.5 rounded text-[10px] bg-neutral-950 border border-neutral-800 text-neutral-500">
                  #{tag}
                </span>
              ))}
            </div>
          )}

          <div className="mt-auto flex items-center gap-1.5 pt-1">
            {isProcessing ? (
              onCancelPipeline ? (
                <button
                  type="button"
                  onClick={() => onCancelPipeline(project.id)}
                  className="flex-1 h-8 rounded-lg border border-neutral-700 text-xs font-semibold text-neutral-200 hover:text-white hover:bg-neutral-800 flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Square className="w-3 h-3 fill-current" /> Stop processing
                </button>
              ) : (
                <span className="flex-1 h-8 flex items-center gap-1.5 text-xs text-neutral-400">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Processing…
                </span>
              )
            ) : (
              <button
                type="button"
                onClick={() => openProject(project)}
                className="flex-1 h-8 rounded-lg bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 text-xs font-semibold text-white flex items-center justify-center gap-1.5 transition-colors"
              >
                {isSelected && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                Open project <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
            {downloadButton(project)}
            {deleteButton(project)}
          </div>
          {exportError?.projectId === project.id && (
            <p role="alert" className="text-[11px] text-rose-300">
              {exportError.message}
            </p>
          )}
        </div>
      </article>
    );
  };

  const renderRow = (project: VideoProject) => {
    const displayName = project.folderName || project.title;
    const isProcessing = project.processingStatus === 'processing';
    const status = projectStatus(project);
    const thumb = projectThumb(project);
    const progress = Math.round(project.processingProgress ?? 0);
    return (
      <li key={project.id} className="group flex items-center gap-3 px-3 sm:px-4 py-3">
        <button
          type="button"
          onClick={() => openProject(project)}
          disabled={isProcessing}
          className="relative w-20 sm:w-24 aspect-video rounded-lg overflow-hidden bg-neutral-800 shrink-0"
          aria-label={`Open ${displayName}`}
        >
          {thumb ? (
            <img src={thumb} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover" />
          ) : (
            <Film className="absolute inset-0 m-auto w-5 h-5 text-neutral-600" />
          )}
        </button>
        <div className="min-w-0 flex-1 space-y-1">
          {renamingProjectId === project.id ? (
            renameField(project)
          ) : (
            <div className="flex items-center gap-1 min-w-0">
              <button
                type="button"
                onClick={() => openProject(project)}
                disabled={isProcessing}
                className="text-left text-[13px] font-semibold text-white truncate hover:text-amber-200 disabled:hover:text-white"
              >
                {displayName}
              </button>
              {renameButton(project, displayName)}
            </div>
          )}
          <div className="flex items-center gap-2 text-[11.5px] text-neutral-500 min-w-0">
            <StatusPill tone={status.tone}>{isProcessing ? `${progress}%` : status.label}</StatusPill>
            <span className="truncate">
              {project.clips.length} clips · {project.duration > 0 ? `${formatMinutes(project.duration)} · ` : ''}
              {formatRelativeTime(project.uploadedAt)}
            </span>
          </div>
          {exportError?.projectId === project.id && (
            <p role="alert" className="text-[11px] text-rose-300">
              {exportError.message}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {isProcessing && onCancelPipeline && (
            <button
              type="button"
              onClick={() => onCancelPipeline(project.id)}
              className="h-8 w-8 flex items-center justify-center rounded-lg border border-neutral-800 text-neutral-300 hover:text-white hover:bg-neutral-800"
              title="Stop processing"
              aria-label="Stop processing"
            >
              <Square className="w-3 h-3 fill-current" />
            </button>
          )}
          {project.sourceUrl && (
            <a
              href={project.sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="hidden sm:flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-800 text-neutral-400 hover:text-amber-300"
              title="Open source video"
              aria-label="Open source video"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
          {downloadButton(project)}
          {deleteButton(project)}
        </div>
      </li>
    );
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <PageHeader
        title="Projects"
        description="One project per long video. Its clips, captions and exports live inside."
        actions={
          <>
            <button
              type="button"
              onClick={() => setIsNewFolderModalOpen(true)}
              className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-[13px] font-semibold text-white transition-colors"
            >
              <FolderPlus className="w-4 h-4 text-amber-400" />
              New folder
              <NotWiredBadge label="Local only" reason="Folders made here are kept in this browser tab only; the backend has no folder endpoint yet, so they disappear on reload." />
            </button>
            <button
              type="button"
              onClick={onOpenUploadModal}
              className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20 transition-colors"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              New video
            </button>
          </>
        }
      />

      {/* Summary */}
      {isLoading ? (
        <StatsSkeleton />
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 rounded-2xl border border-neutral-800 bg-neutral-900/60 [&>div]:border-neutral-800 overflow-hidden">
          {[
            { label: 'projects', value: projects.length },
            { label: 'clips', value: totalClips },
            { label: 'average virality', value: `${avgVirality}` },
            { label: 'of source video', value: `${sourceMinutes} min` },
          ].map((stat, i) => (
            <div
              key={stat.label}
              className={`px-4 py-3 flex items-baseline gap-2 ${i % 2 === 1 ? 'border-l' : ''} ${i >= 2 ? 'border-t lg:border-t-0' : ''} ${i === 2 ? 'lg:border-l' : ''}`}
            >
              <span className="text-lg font-bold text-white tabular-nums">{stat.value}</span>
              <span className="text-xs text-neutral-500">{stat.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Search, status and view */}
      <div className="space-y-3">
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          <div className="relative flex-1 md:max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <label htmlFor="projects-search" className="sr-only">
              Search projects
            </label>
            <input
              id="projects-search"
              type="search"
              placeholder="Search by title, channel or tag"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-9 pl-9 pr-3 rounded-xl bg-neutral-900 border border-neutral-800 text-[13px] text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-500/70"
            />
          </div>
          <div className="flex items-center gap-2 min-w-0">
            <div
              className="inline-flex p-0.5 rounded-xl bg-neutral-900 border border-neutral-800 overflow-x-auto [scrollbar-width:none] min-w-0"
              role="group"
              aria-label="Filter by status"
            >
              {(
                [
                  ['all', 'All'],
                  ['processing', 'Processing'],
                  ['ready', 'Ready'],
                  ['failed', 'Failed'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setStatusFilter(id)}
                  aria-pressed={statusFilter === id}
                  className={`h-8 px-3 rounded-[10px] text-xs font-semibold whitespace-nowrap flex items-center gap-1.5 transition-colors ${
                    statusFilter === id ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'
                  }`}
                >
                  {label}
                  <span className="text-[11px] text-neutral-500 tabular-nums">{statusCounts[id]}</span>
                </button>
              ))}
            </div>
            <div className="ml-auto inline-flex p-0.5 rounded-xl bg-neutral-900 border border-neutral-800 shrink-0" role="group" aria-label="Layout">
              {(
                [
                  ['grid', LayoutGrid, 'Grid'],
                  ['list', List, 'List'],
                ] as const
              ).map(([mode, Icon, label]) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => changeViewMode(mode)}
                  aria-pressed={viewMode === mode}
                  aria-label={`${label} view`}
                  className={`h-8 w-8 rounded-[10px] flex items-center justify-center ${viewMode === mode ? 'bg-neutral-800 text-white' : 'text-neutral-500 hover:text-white'}`}
                >
                  <Icon className="w-4 h-4" />
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto [scrollbar-width:none] -mx-4 px-4 sm:mx-0 sm:px-0">
          {SOURCE_FILTERS.map((f) => chip(f.id, f.label))}
          <span className="w-px h-5 bg-neutral-800 mx-1 shrink-0" aria-hidden="true" />
          <span className="flex items-center gap-1.5 shrink-0 rounded-full border border-dashed border-rose-400/40 pl-1 pr-1.5 py-0.5">
            {TOPIC_FILTERS.map((f) => chip(f.id, f.label))}
            <NotWiredBadge label="Not wired" reason="Projects don't store a topic yet, so these filters never match anything." />
          </span>
        </div>
      </div>

      {/* Projects */}
      {isLoading ? null : filteredProjects.length === 0 ? (
        <div className="p-10 text-center rounded-2xl border border-dashed border-neutral-800 space-y-3">
          <Film className="w-10 h-10 text-neutral-600 mx-auto" />
          <h3 className="text-sm font-semibold text-white">{hasFilters ? 'No projects match these filters' : 'No projects yet'}</h3>
          <p className="text-xs text-neutral-500 max-w-sm mx-auto">
            {hasFilters
              ? 'Try a different search or clear the filters.'
              : 'Paste a YouTube link or upload a long video, and it becomes a project with its clips inside.'}
          </p>
          {hasFilters ? (
            <button
              type="button"
              onClick={clearFilters}
              className="h-9 px-4 rounded-xl border border-neutral-700 text-xs text-amber-300 font-semibold hover:bg-neutral-800"
            >
              Clear filters
            </button>
          ) : (
            <button
              type="button"
              onClick={onOpenUploadModal}
              className="h-9 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold"
            >
              New video
            </button>
          )}
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">{filteredProjects.map(renderCard)}</div>
      ) : (
        <ul className="rounded-2xl border border-neutral-800 bg-neutral-900/60 divide-y divide-neutral-800">
          {filteredProjects.map(renderRow)}
        </ul>
      )}

      {/* New folder dialog */}
      {isNewFolderModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4 bg-black/70 backdrop-blur-sm animate-in fade-in"
          onMouseDown={(e) => e.target === e.currentTarget && setIsNewFolderModalOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-folder-title"
            className="w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl bg-neutral-900 border border-neutral-800 p-5 sm:p-6 shadow-2xl space-y-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]"
          >
            <div className="flex items-start gap-3">
              <span className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
                <FolderPlus className="w-5 h-5" />
              </span>
              <div className="flex-1">
                <h3 id="new-folder-title" className="text-base font-bold text-white">
                  New folder
                </h3>
                <p className="text-xs text-neutral-400">Group clips by show, topic or series</p>
              </div>
              <button
                type="button"
                onClick={() => setIsNewFolderModalOpen(false)}
                className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="flex items-start gap-2 rounded-xl border border-dashed border-rose-400/40 bg-rose-500/5 px-3 py-2 text-[11.5px] text-rose-200">
              <NotWiredBadge label="Local only" reason="No folder endpoint exists yet." className="shrink-0 mt-px" />
              This folder is kept in this tab only and disappears when you reload.
            </p>

            <form onSubmit={handleCreateCustomFolder} className="space-y-4">
              <div>
                <label htmlFor="new-folder-name" className="text-xs font-semibold text-neutral-300 block mb-1.5">
                  Name
                </label>
                <input
                  id="new-folder-name"
                  type="text"
                  placeholder="e.g. Founder Podcast season 2"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  className="w-full h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-700 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-400"
                  required
                  autoFocus
                />
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <span className="text-xs font-semibold text-neutral-300 block mb-1.5">Category</span>
                  <Select
                    value={newFolderCategory}
                    onChange={setNewFolderCategory}
                    options={FOLDER_CATEGORY_OPTIONS}
                    aria-label="Category"
                    className="w-full h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-700 text-sm text-white focus:outline-none focus:border-amber-400"
                  />
                </div>
                <div>
                  <span className="text-xs font-semibold text-neutral-300 block mb-1.5">Color</span>
                  <div className="flex items-center gap-2 h-10" role="radiogroup" aria-label="Folder color">
                    {(Object.keys(FOLDER_COLORS) as FolderColor[]).map((color) => (
                      <button
                        key={color}
                        type="button"
                        role="radio"
                        aria-checked={newFolderColor === color}
                        aria-label={color}
                        onClick={() => setNewFolderColor(color)}
                        className={`w-7 h-7 rounded-full border-2 transition-all ${FOLDER_COLORS[color]} ${
                          newFolderColor === color ? 'border-white scale-110' : 'border-transparent opacity-70 hover:opacity-100'
                        }`}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-neutral-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsNewFolderModalOpen(false)}
                  className="h-9 px-4 rounded-xl text-xs font-semibold text-neutral-300 hover:bg-neutral-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!newFolderName.trim()}
                  className="h-9 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-neutral-950 font-bold text-xs"
                >
                  Create and open
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
