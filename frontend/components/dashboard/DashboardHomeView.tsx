"use client";
import React, { useState } from 'react';
import {
  Sparkles,
  Scissors,
  Film,
  BarChart3,
  CalendarDays,
  Play,
  UploadCloud,
  Youtube,
  Clock,
  Flame,
  ArrowRight,
  Plus,
  Share2,
  Download,
  Zap,
  TrendingUp,
  Sliders,
  CheckCircle2,
  Copy,
  ExternalLink,
  Layers,
  Palette,
  Folder,
  FolderOpen
} from 'lucide-react';
import { VideoProject, ViralClip, UserProfile, TabType } from '@/lib/types';
import { SAMPLE_PROJECTS } from '@/lib/data/mockProjects';

interface DashboardHomeViewProps {
  user: UserProfile;
  activeProject?: VideoProject;
  projects: VideoProject[];
  activeBrandKit?: any;
  onSelectProject: (project: VideoProject) => void;
  onSelectClipForEdit: (clip: ViralClip) => void;
  onScheduleClip: (clip: ViralClip) => void;
  onOpenUpload: () => void;
  onNavigateTab: (tab: TabType) => void;
}

export const DashboardHomeView: React.FC<DashboardHomeViewProps> = ({
  user,
  activeProject,
  projects,
  activeBrandKit,
  onSelectProject,
  onSelectClipForEdit,
  onScheduleClip,
  onOpenUpload,
  onNavigateTab,
}) => {
  const [quickUrl, setQuickUrl] = useState('');
  const [selectedGenreFilter, setSelectedGenreFilter] = useState<string>('all');

  const currentProject = activeProject || projects[0] || SAMPLE_PROJECTS[0];

  // Quick stats calculation
  const totalClipsCount = projects.reduce((acc, p) => acc + (p.clips?.length || 0), 0);
  const avgVirality = Math.round(
    projects.flatMap((p) => p.clips || []).reduce((acc, c) => acc + (c?.viralityScore || 0), 0) /
      (totalClipsCount || 1)
  );

  const filteredProjects =
    selectedGenreFilter === 'all'
      ? projects
      : projects.filter((p) => p.genre.toLowerCase().includes(selectedGenreFilter.toLowerCase()));

  const handleQuickIngest = (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickUrl.trim()) return;
    onOpenUpload();
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* 1. HERO BANNER: Welcome, AI Credit Quota & Ingest Hub */}
      <div className="relative overflow-hidden rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 lg:p-8 shadow-xl">
        {/* Glow ambient background accents */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 blur-3xl pointer-events-none" />
        
        <div className="relative z-10 grid lg:grid-cols-12 gap-6 lg:gap-8 items-center">
          {/* Left Column: Greeting & Quick Action */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/25 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>AI Repurposing Engine Active</span>
              </span>
              <span className="text-xs text-neutral-400">
                Workspace: <strong className="text-neutral-200">Akhil's Creative Studio</strong>
              </span>
            </div>

            <h1 className="text-2xl lg:text-3xl font-extrabold text-white tracking-tight">
              Turn Long Videos Into <span className="text-amber-400">Viral Short Clips</span>
            </h1>

            <p className="text-neutral-300 text-sm leading-relaxed max-w-xl">
              Upload podcasts, webinars, keynote speeches, or YouTube videos. Clipnera extracts top hook moments, auto-generates kinetic captions, centers faces, inserts B-roll, and schedules to TikTok, Instagram Reels, and YouTube Shorts.
            </p>

            {/* Quick URL Ingest Form */}
            <form onSubmit={handleQuickIngest} className="flex flex-col sm:flex-row gap-2 pt-2 max-w-xl">
              <div className="relative flex-1">
                <Youtube className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                <input
                  type="text"
                  placeholder="Paste YouTube, Vimeo, Twitch, or Google Drive link..."
                  value={quickUrl}
                  onChange={(e) => setQuickUrl(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-700/80 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-amber-400 transition-colors shadow-inner"
                />
              </div>
              <button
                type="submit"
                className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center justify-center gap-1.5 shrink-0"
              >
                <Sparkles className="w-4 h-4" />
                <span>Get Clips</span>
              </button>
            </form>
          </div>

          {/* Right Column: Key Metrics & AI Render Quota Card */}
          <div className="lg:col-span-5 grid sm:grid-cols-2 lg:grid-cols-1 gap-3">
            <div className="p-4 rounded-xl bg-neutral-950/90 border border-neutral-800 space-y-3 shadow-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-neutral-300 flex items-center gap-1.5">
                  <Zap className="w-4 h-4 text-amber-400 fill-amber-400" />
                  <span>AI Render Quota ({user.plan.toUpperCase()})</span>
                </span>
                <span className="text-xs font-mono font-bold text-amber-400">
                  {user.aiCreditsMinutesRemaining}m / {user.aiCreditsTotal}m
                </span>
              </div>
              <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-500 transition-all duration-500"
                  style={{
                    width: `${(user.aiCreditsMinutesRemaining / user.aiCreditsTotal) * 100}%`,
                  }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-neutral-400">
                <span>Resets in 18 days</span>
                <button
                  onClick={() => onNavigateTab('settings')}
                  className="text-amber-400 hover:underline font-semibold"
                >
                  Refill Quota +
                </button>
              </div>
            </div>

            {/* Live Studio Quick Jump */}
            <div className="p-4 rounded-xl bg-neutral-950/90 border border-neutral-800 flex items-center justify-between">
              <div>
                <span className="text-[10px] text-amber-400 uppercase font-bold tracking-wider block">
                  Active Project Loaded
                </span>
                <h4 className="text-xs font-bold text-white line-clamp-1 mt-0.5">
                  {currentProject?.title || 'No Project Selected'}
                </h4>
                <p className="text-[11px] text-neutral-400 font-mono">
                  {currentProject?.clips?.length || 0} Viral Shorts Ready
                </p>
              </div>
              <button
                onClick={() => onNavigateTab('generator')}
                className="p-2.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-amber-400 border border-neutral-700 shadow-sm transition-all active:scale-95"
                title="Open Clip Generator"
              >
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 2. STATS KPI BAR */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Total Viral Shorts</span>
            <Film className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{totalClipsCount}</div>
          <p className="text-[11px] text-neutral-400 font-medium">Ready to distribute</p>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Manual Hours Saved</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">38.5 hrs</div>
          <p className="text-[11px] text-neutral-400 font-medium">10x faster workflow</p>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Avg Virality Score</span>
            <Flame className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{avgVirality} / 100</div>
          <p className="text-[11px] text-amber-400 font-medium">Top 2% AI benchmark</p>
        </div>

        <div className="p-4 rounded-xl bg-neutral-900/80 border border-neutral-800 space-y-1">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-medium">Best Post Window</span>
            <CalendarDays className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">7:15 PM</div>
          <p className="text-[11px] text-neutral-400 font-medium">TikTok & IG Peak</p>
        </div>
      </div>

      {/* 3. FEATURED VIRAL SHORTS */}
      <div className="space-y-3.5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base lg:text-lg font-bold text-white">
              Top AI-Ranked Viral Clips
            </h2>
            <p className="text-xs text-neutral-400">
              Highest hook score clips extracted from your current long video projects
            </p>
          </div>

          <button
            onClick={() => onNavigateTab('generator')}
            className="text-xs text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1"
          >
            <span>View All ({currentProject?.clips?.length || 0})</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {(currentProject?.clips || []).slice(0, 4).map((clip) => (
            <div
              key={clip.id}
              className="group rounded-xl bg-neutral-900 border border-neutral-800 overflow-hidden hover:border-neutral-700 transition-all shadow-md flex flex-col"
            >
              {/* Top Video Preview / Thumbnail */}
              <div className="relative aspect-[9/16] bg-neutral-950 overflow-hidden max-h-56">
                <img
                  src={clip.posterUrl || currentProject?.posterUrl}
                  alt={clip.title}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-neutral-950 via-transparent to-black/30" />

                {/* Virality Badge */}
                <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-lg bg-neutral-950/85 backdrop-blur-md border border-amber-500/40 text-amber-300 text-xs font-mono font-bold flex items-center gap-1">
                  <Flame className="w-3 h-3 text-amber-400" />
                  <span>{clip.viralityScore}/100</span>
                </div>

                {/* Duration Badge */}
                <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-lg bg-black/70 backdrop-blur-md text-[10px] font-mono text-neutral-300">
                  {clip.duration}s
                </div>

                {/* Subtitle Style Overlay Preview */}
                <div className="absolute bottom-3 left-3 right-3 text-center">
                  <span className="inline-block px-2.5 py-1 rounded-md bg-black/85 backdrop-blur-sm text-[11px] font-black text-amber-400 uppercase tracking-tight shadow-md">
                    "{clip.hook ? clip.hook.slice(0, 45) : ''}..."
                  </span>
                </div>
              </div>

              {/* Clip Details */}
              <div className="p-3.5 flex-1 flex flex-col justify-between space-y-3">
                <div>
                  <h3 className="text-xs font-bold text-white line-clamp-2 group-hover:text-amber-300 transition-colors">
                    {clip.title}
                  </h3>
                  <p className="text-[11px] text-neutral-400 line-clamp-2 mt-1">
                    {clip.rationale}
                  </p>
                </div>

                {/* Action Buttons */}
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-neutral-800/80">
                  <button
                    onClick={() => onSelectClipForEdit(clip)}
                    className="py-2 px-2.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-white font-medium text-xs transition-colors flex items-center justify-center gap-1.5"
                  >
                    <Scissors className="w-3.5 h-3.5 text-neutral-300" />
                    <span>Edit</span>
                  </button>

                  <button
                    onClick={() => onScheduleClip(clip)}
                    className="py-2 px-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/25 font-medium text-xs transition-colors flex items-center justify-center gap-1.5"
                  >
                    <CalendarDays className="w-3.5 h-3.5" />
                    <span>Schedule</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. ALL PROJECTS & REPURPOSING PIPELINE */}
      <div className="space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <FolderOpen className="w-5 h-5 text-amber-400" />
              <h2 className="text-base lg:text-lg font-bold text-white">
                Project Folders & Video Library
              </h2>
            </div>
            <p className="text-xs text-neutral-400">
              Each ingested YouTube link or uploaded video forms a dedicated folder with viral short clips inside
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onNavigateTab('folders')}
              className="px-3.5 py-1.5 rounded-xl bg-neutral-900 hover:bg-neutral-800 text-neutral-300 hover:text-white font-semibold text-xs border border-neutral-800 transition-colors flex items-center gap-1.5"
            >
              <Folder className="w-3.5 h-3.5 text-amber-400" />
              <span>Browse All Folders ({projects.length})</span>
            </button>

            <button
              onClick={onOpenUpload}
              className="px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>New Video Folder</span>
            </button>
          </div>
        </div>

        {/* Projects Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredProjects.map((p) => {
            const isSelected = p.id === currentProject?.id;
            const folderDisplayName = p.folderName || p.title;

            return (
              <div
                key={p.id}
                onClick={() => {
                  onSelectProject(p);
                  onNavigateTab('generator');
                }}
                className={`cursor-pointer rounded-xl p-4 border transition-all relative overflow-hidden flex flex-col justify-between group ${
                  isSelected
                    ? 'bg-neutral-900 border-amber-500/60 ring-1 ring-amber-500/30 shadow-lg'
                    : 'bg-neutral-900/70 border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-neutral-800 text-amber-400 flex items-center gap-1">
                      <Folder className="w-3 h-3" />
                      <span>{p.folderCategory || p.genre}</span>
                    </span>
                    <span className="text-[11px] font-mono text-neutral-400">
                      {Math.floor(p.duration / 60)}m {p.duration % 60}s
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-white mt-2.5 line-clamp-1 group-hover:text-amber-300 transition-colors">
                    {folderDisplayName}
                  </h3>

                  <p className="text-xs text-neutral-400 mt-1 line-clamp-2">
                    {p.clips[0]?.hook ? `"${p.clips[0].hook}"` : (p.description || 'AI virality analysis completed with multi-speaker detection.')}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-neutral-800 flex items-center justify-between text-xs">
                  <span className="font-mono text-amber-400 font-semibold flex items-center gap-1">
                    <span>{p.clips.length} Short Videos</span>
                  </span>

                  <div className="flex items-center gap-2">
                    {isSelected && (
                      <span className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Active
                      </span>
                    )}
                    <span className="text-neutral-300 group-hover:text-white font-medium flex items-center gap-1 text-[11px]">
                      <span>Open Folder</span>
                      <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. FAST SHORTCUTS FOOTER */}
      <div className="grid sm:grid-cols-3 gap-4 pt-2">
        <div
          onClick={() => onNavigateTab('brand_kit')}
          className="cursor-pointer p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900 transition-all flex items-center gap-3.5"
        >
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Palette className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-white">Brand Kit Presets</h4>
            <p className="text-[11px] text-neutral-400">Custom fonts, watermark logo & colors</p>
          </div>
        </div>

        <div
          onClick={() => onNavigateTab('scheduler')}
          className="cursor-pointer p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900 transition-all flex items-center gap-3.5"
        >
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <CalendarDays className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-white">Social Scheduler</h4>
            <p className="text-[11px] text-neutral-400">TikTok, IG Reels & YouTube Shorts queue</p>
          </div>
        </div>

        <div
          onClick={() => onNavigateTab('analytics')}
          className="cursor-pointer p-4 rounded-xl bg-neutral-900/60 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900 transition-all flex items-center gap-3.5"
        >
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-white">Virality Analytics</h4>
            <p className="text-[11px] text-neutral-400">Retention curves & hook simulator</p>
          </div>
        </div>
      </div>
    </div>
  );
};
