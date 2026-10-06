"use client";
import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  BarChart3,
  CalendarDays,
  Check,
  Clock,
  Crown,
  Film,
  Flame,
  FolderOpen,
  Link as LinkIcon,
  Loader2,
  Palette,
  Plus,
  Scissors,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';
import { VideoProject, ViralClip, UserProfile, TabType, Workspace } from '@/lib/types';
import { analyticsApi, brandKitApi, socialApi, type DashboardStatsResponse, type SocialPostResponse } from '@/lib/api';
import { StatsSkeleton } from '@/components/skeletons';
import { usePlan } from '@/hooks/usePlan';
import { InvitedByCard } from '@/components/referral/InvitedByCard';
import { creditResetLabel, creditSplit, useEntitlements, videoMinutesFor } from '@/hooks/useEntitlements';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { extractYoutubeVideoId } from '@/lib/utils/urlParser';
import { formatRelativeTime, formatScheduleTime, parseApiDate } from '@/lib/utils/dates';
import { PageHeader } from '@/components/ui/PageHeader';
import { StatusPill, projectStatus } from '@/components/ui/StatusPill';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { NotWiredBadge } from '@/components/ui/NotWiredBadge';
import { PLATFORM_STYLE, SOCIAL_SETTINGS_PATH } from '@/components/social/platforms';
import { ClipPoster } from './ClipPoster';

export interface OpenUploadOptions {
  url?: string;
  mode?: 'youtube' | 'upload';
}

interface DashboardHomeViewProps {
  user: UserProfile;
  projects: VideoProject[];
  workspaces: Workspace[];
  projectsLoading?: boolean;
  onSelectProject: (project: VideoProject) => void;
  onOpenClip: (clip: ViralClip, project: VideoProject) => void;
  onScheduleClip: (clip: ViralClip) => void;
  onOpenUpload: (options?: OpenUploadOptions) => void;
  onCancelPipeline: (projectId: string) => void;
  onNavigateTab: (tab: TabType) => void;
  onUpgradePlan?: () => void;
}

const CHECKLIST_DISMISSED_KEY = 'clipnera.setupChecklistDismissed';

const greetingFor = (date: Date) => {
  const hour = date.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
};

export const DashboardHomeView: React.FC<DashboardHomeViewProps> = ({
  user,
  projects,
  workspaces,
  projectsLoading = false,
  onSelectProject,
  onOpenClip,
  onScheduleClip,
  onOpenUpload,
  onCancelPipeline,
  onNavigateTab,
  onUpgradePlan,
}) => {
  const router = useRouter();
  const { isPro, hasPendingPayment } = usePlan();
  const { entitlements } = useEntitlements();
  const { flags } = useFeatureFlags();
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [link, setLink] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const [upcoming, setUpcoming] = useState<SocialPostResponse[] | null>(null);
  const [hasConnectedAccount, setHasConnectedAccount] = useState<boolean | null>(null);
  const [brandCustomized, setBrandCustomized] = useState<boolean | null>(null);
  const [checklistDismissed, setChecklistDismissed] = useState(true);
  const [greeting, setGreeting] = useState('Welcome back');

  const upgrade = onUpgradePlan || (() => onNavigateTab('settings'));

  useEffect(() => {
    // Time of day is only known on the client; set it after mount so the
    // server render matches.
    setGreeting(greetingFor(new Date()));
    try {
      setChecklistDismissed(localStorage.getItem(CHECKLIST_DISMISSED_KEY) === '1');
    } catch {
      setChecklistDismissed(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    analyticsApi
      .getDashboardStats()
      .then((data) => !cancelled && setStats(data))
      .catch(() => {
        if (!cancelled) {
          setStats({ total_viral_shorts: 0, manual_hours_saved: 0, avg_virality_score: 0, best_post_window: '7:00 PM' });
        }
      });
    brandKitApi
      .getMe()
      .then((kit) => !cancelled && setBrandCustomized(kit.isCustomized))
      .catch(() => !cancelled && setBrandCustomized(null));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!flags.social_publishing) return;
    let cancelled = false;
    socialApi
      .listPosts(['scheduled', 'publishing', 'published'], 10)
      .then((res) => {
        if (cancelled) return;
        const now = Date.now();
        const next = res.posts
          .filter((p) => p.status !== 'published' || now - parseApiDate(p.published_at || p.scheduled_at).getTime() < 3 * 86_400_000)
          .sort((a, b) => parseApiDate(a.scheduled_at).getTime() - parseApiDate(b.scheduled_at).getTime())
          .slice(0, 3);
        setUpcoming(next);
      })
      .catch(() => !cancelled && setUpcoming([]));
    socialApi
      .getConnections()
      .then((res) => !cancelled && setHasConnectedAccount(res.accounts.some((a) => a.status === 'active')))
      .catch(() => !cancelled && setHasConnectedAccount(null));
    return () => {
      cancelled = true;
    };
  }, [flags.social_publishing]);

  const activeWorkspace = workspaces.find((ws) => ws.id === user.activeWorkspaceId) || workspaces[0];
  const firstName = (user.name || '').trim().split(/\s+/)[0];
  const processing = projects.filter((p) => p.processingStatus === 'processing');
  const totalClips = projects.reduce((acc, p) => acc + (p.clips?.length || 0), 0);

  // The best clips across every finished project, not only the open one.
  const topClips = useMemo(
    () =>
      projects
        .filter((p) => p.processingStatus !== 'processing')
        .flatMap((project) => project.clips.map((clip) => ({ clip, project })))
        .sort((a, b) => b.clip.viralityScore - a.clip.viralityScore)
        .slice(0, 5),
    [projects],
  );

  const checklist = [
    { id: 'clips', label: 'Create your first clips', done: totalClips > 0, action: () => onOpenUpload() },
    ...(flags.social_publishing
      ? [{ id: 'social', label: 'Connect a social account', done: hasConnectedAccount === true, action: () => router.push(SOCIAL_SETTINGS_PATH) }]
      : []),
    { id: 'brand', label: 'Set your brand colors and watermark', done: brandCustomized === true, action: () => onNavigateTab('brand_kit') },
    ...(flags.social_publishing
      ? [{ id: 'post', label: 'Schedule or publish a clip', done: (upcoming?.length ?? 0) > 0, action: () => onNavigateTab('scheduler') }]
      : []),
  ];
  const doneCount = checklist.filter((item) => item.done).length;
  const showChecklist = !checklistDismissed && !projectsLoading && doneCount < checklist.length;

  const dismissChecklist = () => {
    setChecklistDismissed(true);
    try {
      localStorage.setItem(CHECKLIST_DISMISSED_KEY, '1');
    } catch {
      // A private window may refuse storage; hiding for this visit is enough.
    }
  };

  const submitLink = (e: React.FormEvent) => {
    e.preventDefault();
    const url = link.trim();
    if (!url) {
      onOpenUpload({ mode: 'youtube' });
      return;
    }
    if (!extractYoutubeVideoId(url)) {
      setLinkError('That doesn’t look like a YouTube link. Try one like youtube.com/watch?v=…');
      return;
    }
    setLinkError(null);
    onOpenUpload({ url, mode: 'youtube' });
    setLink('');
  };

  const total = Math.max(user.aiCreditsTotal, user.aiCreditsMinutesRemaining, 1);
  const { plan: planCredits, bonus, bought } = creditSplit(entitlements, user.aiCreditsMinutesRemaining);

  return (
    <div className="space-y-6 lg:space-y-8 animate-in fade-in duration-300">
      <PageHeader
        title={`${greeting}${firstName ? `, ${firstName}` : ''}`}
        description={
          <>
            {activeWorkspace?.name || 'Your workspace'} · {projects.length} {projects.length === 1 ? 'project' : 'projects'} ·{' '}
            {totalClips} {totalClips === 1 ? 'clip' : 'clips'}
          </>
        }
        actions={
          <>
            <button
              type="button"
              onClick={() => onOpenUpload({ mode: 'upload' })}
              className="hidden sm:inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-[13px] font-semibold text-white transition-colors"
            >
              <Upload className="w-4 h-4" />
              Upload file
            </button>
            <button
              type="button"
              onClick={() => onOpenUpload()}
              className="hidden sm:inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20 transition-colors"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              New video
            </button>
          </>
        }
      />

      <InvitedByCard onGetPro={upgrade} />

      {/* Start from a link, right here */}
      <form onSubmit={submitLink} className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-2.5 sm:p-3">
        <div className="flex flex-col sm:flex-row gap-2.5">
          <label htmlFor="home-youtube-link" className="sr-only">
            YouTube link
          </label>
          <div className="flex-1 flex items-center gap-2.5 h-11 px-3.5 rounded-xl bg-neutral-950 border border-neutral-800 focus-within:border-amber-500/70 focus-within:ring-2 focus-within:ring-amber-500/15 transition-colors">
            <LinkIcon className="w-4 h-4 text-neutral-500 shrink-0" />
            <input
              id="home-youtube-link"
              value={link}
              onChange={(e) => {
                setLink(e.target.value);
                setLinkError(null);
              }}
              placeholder="Paste a YouTube link to get clips"
              inputMode="url"
              autoComplete="off"
              className="flex-1 min-w-0 bg-transparent text-sm text-white placeholder:text-neutral-500 focus:outline-none"
              aria-invalid={Boolean(linkError)}
              aria-describedby={linkError ? 'home-link-error' : 'home-link-hint'}
            />
          </div>
          <button
            type="submit"
            className="h-11 px-5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-sm font-bold flex items-center justify-center gap-2 shadow-md shadow-amber-500/20 transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            Get clips
          </button>
        </div>
        {linkError ? (
          <p id="home-link-error" className="mt-2 px-1 text-xs text-rose-300">
            {linkError}
          </p>
        ) : (
          <p id="home-link-hint" className="mt-2 px-1 text-[11.5px] text-neutral-500">
            {entitlements.credits_per_video_minute} credit{entitlements.credits_per_video_minute === 1 ? '' : 's'} per minute of video · you’ll confirm formats and cost before anything is charged
          </p>
        )}
      </form>

      {/* What is running now, and what it costs */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {processing.length > 0 ? (
          <section className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-4 sm:p-5 space-y-4" aria-label="Processing">
            {processing.slice(0, 3).map((project) => {
              const pct = Math.round(project.processingProgress || 0);
              return (
                <div key={project.id} className="space-y-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill tone="processing">Processing</StatusPill>
                    <span className="font-semibold text-white text-sm truncate min-w-0 flex-1">
                      {project.folderName || project.title}
                    </span>
                    <span className="text-sm font-bold text-amber-300 tabular-nums">{pct}%</span>
                  </div>
                  <div
                    className="h-2 w-full rounded-full bg-neutral-800 overflow-hidden"
                    role="progressbar"
                    aria-valuenow={pct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${project.folderName || project.title} progress`}
                  >
                    <div className="h-full bg-amber-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onNavigateTab('folders')}
                      className="h-8 px-3 rounded-lg border border-neutral-700 bg-neutral-800/60 hover:bg-neutral-800 text-xs font-semibold text-white transition-colors"
                    >
                      View progress
                    </button>
                    <button
                      type="button"
                      onClick={() => onCancelPipeline(project.id)}
                      className="h-8 px-3 rounded-lg text-xs font-semibold text-neutral-400 hover:text-rose-300 transition-colors"
                    >
                      Cancel
                    </button>
                    <span className="ml-auto text-[11.5px] text-neutral-500">We’ll notify you when the clips are ready</span>
                  </div>
                </div>
              );
            })}
            {processing.length > 3 && (
              <button type="button" onClick={() => onNavigateTab('folders')} className="text-xs font-semibold text-amber-400">
                +{processing.length - 3} more processing
              </button>
            )}
          </section>
        ) : (
          <section className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-4 sm:p-5 flex items-center gap-4" aria-label="Processing">
            <span className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center shrink-0">
              <Check className="w-5 h-5" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">Nothing processing</p>
              <p className="text-xs text-neutral-400">Paste a link or upload a video and it will show up here while it runs.</p>
            </div>
          </section>
        )}

        <section className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-4 sm:p-5 space-y-3" aria-label="Credits">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-white">Credits</h2>
            <span className="flex-1" />
            {isPro ? (
              <StatusPill tone="processing" dot={false}>
                <Crown className="w-3 h-3" />
                {user.plan === 'pro_plus' ? 'Pro Plus' : 'Pro'}
              </StatusPill>
            ) : (
              <StatusPill tone="neutral" dot={false}>
                Free plan
              </StatusPill>
            )}
          </div>
          <p className="text-2xl font-bold text-white tabular-nums">
            {user.aiCreditsMinutesRemaining}
            <span className="text-sm font-medium text-neutral-500"> of {user.aiCreditsTotal} left</span>
          </p>
          <div className="h-2 w-full rounded-full bg-neutral-800 overflow-hidden flex">
            <div className="h-full bg-amber-500" style={{ width: `${(planCredits / total) * 100}%` }} />
            <div className="h-full bg-sky-400" style={{ width: `${(bonus / total) * 100}%` }} />
            <div className="h-full bg-violet-400" style={{ width: `${(bought / total) * 100}%` }} />
          </div>
          <p className="text-[11.5px] text-neutral-400">
            ≈ {videoMinutesFor(entitlements, user.aiCreditsMinutesRemaining)} min of video · {creditResetLabel(entitlements.next_credit_reset_at).toLowerCase()}
            {bonus > 0 && <> · {bonus} bonus credits</>}
            {bought > 0 && <> · {bought} bought credits never expire</>}
          </p>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="button"
              onClick={upgrade}
              className="h-8 px-3 rounded-lg border border-neutral-700 bg-neutral-800/60 hover:bg-neutral-800 text-xs font-semibold text-white transition-colors"
            >
              Buy credits
            </button>
            {!isPro &&
              (hasPendingPayment ? (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-amber-300">
                  <Clock className="w-3.5 h-3.5" /> Pro activation pending
                </span>
              ) : (
                <button
                  type="button"
                  onClick={upgrade}
                  className="h-8 px-3 rounded-lg bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold transition-colors"
                >
                  Upgrade to Pro
                </button>
              ))}
          </div>
        </section>
      </div>

      {/* Headline numbers */}
      {stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'Clips created', value: `${stats.total_viral_shorts}`, hint: 'ready to post', icon: Film },
            { label: 'Editing time saved', value: `${stats.manual_hours_saved}`, unit: 'hours', hint: 'compared with cutting by hand', icon: Clock },
            { label: 'Average virality', value: `${stats.avg_virality_score}`, unit: '/ 100', hint: 'across all clips', icon: Flame },
            { label: 'Best time to post', value: stats.best_post_window, hint: 'TikTok and Instagram peak', icon: CalendarDays },
          ].map((kpi) => {
            const Icon = kpi.icon;
            return (
              <div key={kpi.label} className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-4">
                <div className="flex items-center justify-between text-xs font-medium text-neutral-400">
                  <span>{kpi.label}</span>
                  <Icon className="w-4 h-4 text-neutral-500" />
                </div>
                <p className="mt-2 text-xl sm:text-2xl font-bold text-white tabular-nums tracking-tight">
                  {kpi.value}
                  {kpi.unit && <span className="text-sm font-semibold text-neutral-500"> {kpi.unit}</span>}
                </p>
                <p className="text-[11.5px] text-neutral-500 mt-0.5">{kpi.hint}</p>
              </div>
            );
          })}
        </div>
      ) : (
        <StatsSkeleton />
      )}

      {/* Top clips */}
      <section className="space-y-3.5" aria-labelledby="home-top-clips">
        <div className="flex items-baseline gap-3">
          <h2 id="home-top-clips" className="text-base font-bold text-white">
            Top clips
          </h2>
          <span className="text-xs text-neutral-500">ranked by virality</span>
          {topClips.length > 0 && (
            <button
              type="button"
              onClick={() => onNavigateTab('folders')}
              className="ml-auto text-xs font-semibold text-amber-400 hover:text-amber-300 flex items-center gap-1"
            >
              All projects <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {topClips.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
            {topClips.map(({ clip, project }) => (
              <article
                key={clip.id}
                className="group rounded-2xl bg-neutral-900 border border-neutral-800 hover:border-neutral-700 overflow-hidden flex flex-col transition-colors"
              >
                <button
                  type="button"
                  onClick={() => onOpenClip(clip, project)}
                  className="block text-left"
                  aria-label={`Edit ${clip.title}`}
                >
                  <ClipPoster clip={clip} pendingLabel="Poster rendering…">
                    <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30" />
                    <ScoreRing score={clip.viralityScore} className="absolute top-2 right-2 h-9 w-9" />
                    <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-white">
                      {clip.duration}s
                    </span>
                  </ClipPoster>
                </button>
                <div className="p-3 flex-1 flex flex-col gap-2">
                  <h3 className="text-[13px] font-semibold text-white leading-snug line-clamp-2" title={clip.title}>
                    {clip.title}
                  </h3>
                  <p className="text-[11px] text-neutral-500 truncate">{project.folderName || project.title}</p>
                  <div className="mt-auto flex items-center gap-1.5 pt-1">
                    <button
                      type="button"
                      onClick={() => onOpenClip(clip, project)}
                      className="flex-1 h-8 rounded-lg border border-neutral-700 bg-neutral-800/70 hover:bg-neutral-700 text-[11.5px] font-semibold text-white flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <Scissors className="w-3.5 h-3.5" /> Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => onScheduleClip(clip)}
                      title="Schedule post"
                      aria-label={`Schedule ${clip.title}`}
                      className="h-8 w-8 rounded-lg border border-neutral-700 bg-neutral-800/70 hover:bg-neutral-700 text-amber-400 flex items-center justify-center transition-colors"
                    >
                      <CalendarDays className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-neutral-800 p-8 text-center space-y-3">
            <Film className="w-9 h-9 text-neutral-600 mx-auto" />
            <h3 className="text-sm font-semibold text-neutral-200">No clips yet</h3>
            <p className="text-xs text-neutral-500 max-w-sm mx-auto">
              {processing.length > 0
                ? 'Your first clips will appear here as soon as processing finishes.'
                : 'Paste a YouTube link above or upload a long video to get your first ranked clips.'}
            </p>
          </div>
        )}
      </section>

      {/* Up next and setup */}
      {(flags.social_publishing || showChecklist) && (
        <div className={`grid grid-cols-1 gap-4 ${flags.social_publishing && showChecklist ? 'lg:grid-cols-2' : ''}`}>
          {flags.social_publishing && (
            <section className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-4 sm:p-5" aria-labelledby="home-up-next">
              <div className="flex items-center gap-2 mb-2">
                <h2 id="home-up-next" className="text-sm font-bold text-white">
                  Up next
                </h2>
                <span className="flex-1" />
                <button
                  type="button"
                  onClick={() => onNavigateTab('scheduler')}
                  className="text-xs font-semibold text-amber-400 hover:text-amber-300"
                >
                  Open scheduler
                </button>
              </div>
              {upcoming === null ? (
                <div className="flex items-center gap-2 py-6 text-xs text-neutral-500">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading posts…
                </div>
              ) : upcoming.length === 0 ? (
                <p className="py-6 text-xs text-neutral-500">
                  Nothing scheduled. Pick a clip and choose when it goes out.
                </p>
              ) : (
                <ul className="divide-y divide-neutral-800">
                  {upcoming.map((post) => (
                    <li key={post.id} className="flex items-center gap-3 py-2.5">
                      <span
                        className={`w-7 h-7 rounded-lg bg-gradient-to-br ${PLATFORM_STYLE[post.platform].color} flex items-center justify-center text-[9px] font-extrabold text-white shrink-0`}
                        aria-label={PLATFORM_STYLE[post.platform].name}
                      >
                        {PLATFORM_STYLE[post.platform].short}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] font-semibold text-white truncate">{post.clip_title}</span>
                        <span className="block text-[11.5px] text-neutral-500 truncate">
                          {post.status === 'published'
                            ? `Posted ${formatRelativeTime(post.published_at || post.scheduled_at)}`
                            : formatScheduleTime(post.scheduled_at)}
                          {post.account_handle ? ` · ${post.account_handle}` : ''}
                        </span>
                      </span>
                      <StatusPill tone={post.status === 'published' ? 'ready' : post.status === 'publishing' ? 'processing' : 'scheduled'}>
                        {post.status === 'published' ? 'Published' : post.status === 'publishing' ? 'Publishing' : 'Scheduled'}
                      </StatusPill>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {showChecklist && (
            <section className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-4 sm:p-5" aria-labelledby="home-setup">
              <div className="flex items-center gap-2 mb-3">
                <h2 id="home-setup" className="text-sm font-bold text-white">
                  Get set up
                </h2>
                <span className="text-xs text-neutral-500 tabular-nums">
                  {doneCount} of {checklist.length} done
                </span>
                <span className="flex-1" />
                <button
                  type="button"
                  onClick={dismissChecklist}
                  className="p-1 rounded-md text-neutral-500 hover:text-white hover:bg-neutral-800"
                  aria-label="Hide setup checklist"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="h-1.5 rounded-full bg-neutral-800 overflow-hidden mb-2">
                <div className="h-full bg-emerald-400 transition-all" style={{ width: `${(doneCount / checklist.length) * 100}%` }} />
              </div>
              <ul className="divide-y divide-neutral-800">
                {checklist.map((item) => (
                  <li key={item.id} className="flex items-center gap-3 py-2.5">
                    <span
                      className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ${
                        item.done ? 'bg-emerald-500 border-emerald-500 text-neutral-950' : 'border-neutral-600'
                      }`}
                      aria-hidden="true"
                    >
                      {item.done && <Check className="w-3 h-3 stroke-[3]" />}
                    </span>
                    <span className={`flex-1 text-[13px] ${item.done ? 'text-neutral-500 line-through' : 'text-white font-medium'}`}>
                      {item.label}
                      <span className="sr-only">{item.done ? ' (done)' : ''}</span>
                    </span>
                    {!item.done && (
                      <button
                        type="button"
                        onClick={item.action}
                        className="h-7 px-2.5 rounded-lg border border-neutral-700 text-[11.5px] font-semibold text-white hover:bg-neutral-800"
                      >
                        Start
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {/* Recent projects */}
      <section className="space-y-3.5" aria-labelledby="home-projects">
        <div className="flex items-center gap-3">
          <h2 id="home-projects" className="text-base font-bold text-white">
            Recent projects
          </h2>
          <span className="flex-1" />
          <button
            type="button"
            onClick={() => onNavigateTab('folders')}
            className="text-xs font-semibold text-amber-400 hover:text-amber-300 flex items-center gap-1"
          >
            Browse all ({projects.length}) <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {projects.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-neutral-800 p-8 text-center space-y-3">
            <FolderOpen className="w-9 h-9 text-neutral-600 mx-auto" />
            <h3 className="text-sm font-semibold text-neutral-200">No projects yet</h3>
            <p className="text-xs text-neutral-500 max-w-sm mx-auto">
              Each video you add becomes a project with its clips, captions and exports inside.
            </p>
            <button
              type="button"
              onClick={() => onOpenUpload()}
              className="h-9 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold"
            >
              Create your first project
            </button>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
            {projects.slice(0, 3).map((p) => {
              const status = projectStatus(p);
              const isProcessing = p.processingStatus === 'processing';
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => (isProcessing ? onNavigateTab('folders') : onSelectProject(p))}
                  className="group text-left rounded-2xl bg-neutral-900/80 border border-neutral-800 hover:border-neutral-700 p-3 flex gap-3 items-center transition-colors"
                >
                  <span className="relative w-20 aspect-video rounded-lg overflow-hidden bg-neutral-800 shrink-0">
                    {p.posterUrl ? (
                      <img src={p.posterUrl} alt="" className="absolute inset-0 w-full h-full object-cover" loading="lazy" />
                    ) : (
                      <Film className="absolute inset-0 m-auto w-5 h-5 text-neutral-600" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1 space-y-1">
                    <span className="block text-[13px] font-semibold text-white truncate group-hover:text-amber-200">
                      {p.folderName || p.title}
                    </span>
                    <span className="flex items-center gap-2">
                      <StatusPill tone={status.tone}>
                        {isProcessing ? `${Math.round(p.processingProgress || 0)}%` : status.label}
                      </StatusPill>
                      <span className="text-[11px] text-neutral-500 truncate">
                        {p.clips.length} clips · {formatRelativeTime(p.uploadedAt)}
                      </span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Shortcuts */}
      <div className="grid sm:grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => onNavigateTab('brand_kit')}
          className="text-left p-4 rounded-2xl bg-neutral-900/60 border border-neutral-800 hover:border-neutral-700 transition-colors flex items-center gap-3.5"
        >
          <span className="w-9 h-9 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
            <Palette className="w-4 h-4" />
          </span>
          <span>
            <span className="block text-[13px] font-semibold text-white">Brand kit</span>
            <span className="block text-[11.5px] text-neutral-500">Fonts, watermark, colors and caption style</span>
          </span>
        </button>
        <button
          type="button"
          onClick={() => onNavigateTab('analytics')}
          className="text-left p-4 rounded-2xl bg-neutral-900/60 border border-neutral-800 hover:border-neutral-700 transition-colors flex items-center gap-3.5"
        >
          <span className="w-9 h-9 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
            <BarChart3 className="w-4 h-4" />
          </span>
          <span className="flex-1">
            <span className="flex items-center gap-2 text-[13px] font-semibold text-white">
              Analytics
              <NotWiredBadge label="Sample data" reason="Analytics shows example numbers; it is not connected to platform analytics yet." />
            </span>
            <span className="block text-[11.5px] text-neutral-500">Retention curves and hook tester</span>
          </span>
        </button>
      </div>
    </div>
  );
};
