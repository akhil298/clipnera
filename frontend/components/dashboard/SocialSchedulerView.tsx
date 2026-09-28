"use client";
import React, { useState, useEffect, useCallback } from 'react';
import { Clock, Sparkles, Copy, Check, Globe, Plus } from 'lucide-react';
import { ViralClip } from '@/lib/types';
import { socialApi, type SocialPostResponse } from '@/lib/api';
import { DEFAULT_TIMEZONE } from '@/lib/utils/timezones';
import { PublishComposer } from '@/components/social/PublishComposer';
import { ScheduledPostsQueue } from '@/components/social/ScheduledPostsQueue';
import { Select, SelectOption } from '@/components/ui/Select';
import { PageHeader } from '@/components/ui/PageHeader';
import { NotWiredBadge } from '@/components/ui/NotWiredBadge';
import { PostCalendar } from '@/components/social/PostCalendar';

const TIMEZONE_OPTIONS: SelectOption<string>[] = [
  { value: 'America/New_York', label: 'Eastern Time (EST / US)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PST / US)' },
  { value: 'Europe/London', label: 'London / GMT' },
  { value: 'Europe/Berlin', label: 'Central European (CET)' },
  { value: 'Asia/Singapore', label: 'Singapore / SGT' },
  { value: 'Asia/Kolkata', label: 'India / IST' },
];

interface SocialSchedulerViewProps {
  clips?: ViralClip[];
  selectedClip?: ViralClip | null;
  onSelectClip?: (clip: ViralClip) => void;
}

export const SocialSchedulerView: React.FC<SocialSchedulerViewProps> = ({
  clips = [],
  selectedClip,
  onSelectClip,
}) => {
  const fallbackClip = selectedClip || clips?.[0];
  const [posts, setPosts] = useState<SocialPostResponse[] | null>(null);
  const [activeClip, setActiveClip] = useState<ViralClip | undefined>(fallbackClip);
  const [selectedTimezone, setSelectedTimezone] = useState(DEFAULT_TIMEZONE);
  const [selectedPlatform, setSelectedPlatform] = useState<'tiktok' | 'instagram' | 'youtube' | 'x'>('tiktok');
  const [isGeneratingHooks, setIsGeneratingHooks] = useState(false);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  useEffect(() => {
    if (selectedClip) {
      setActiveClip(selectedClip);
    } else if (clips && clips.length > 0) {
      setActiveClip(clips[0]);
    }
  }, [selectedClip, clips]);

  // AI Hook variations
  const [generatedHooks, setGeneratedHooks] = useState(
    activeClip?.socialOptimization?.optimizedHooks || [
      {
        type: 'Curiosity Gap',
        text: activeClip?.hook || 'What nobody tells you about this topic...',
        strength: 99,
        predictedRetention: '+41%',
      },
      {
        type: 'Contrarian Take',
        text: 'Stop editing videos manually in 2026. Do this instead.',
        strength: 95,
        predictedRetention: '+33%',
      },
      {
        type: 'MrBeast Fast-Paced',
        text: 'In 30 seconds I will reveal how to double your short-form watch time!',
        strength: 97,
        predictedRetention: '+38%',
      },
    ]
  );

  const [customCaption, setCustomCaption] = useState(
    `${activeClip?.hook || activeClip?.title || 'Your caption'}\n\nHere's the step-by-step breakdown. Drop a comment below if you want the full AI prompt checklist! 👇`
  );

  // Platform AI Timing data
  const PLATFORM_TIMINGS = [
    {
      platform: 'tiktok' as const,
      name: 'TikTok',
      color: 'from-pink-500 to-rose-600',
      optimalWindow: '7:15 PM - 9:00 PM',
      bestDays: ['Tuesday', 'Thursday', 'Saturday'],
      reachBoost: '2.4x Higher Feed Velocity',
      algorithmInsight: 'Evening scrolling surges boost retention on fast-paced kinetic subtitles.',
      hashtags: ['#creatorhacks', '#clipnera', '#fyp', '#viralgrowth', '#shorts'],
    },
    {
      platform: 'instagram' as const,
      name: 'Instagram Reels',
      color: 'from-purple-500 to-pink-500',
      optimalWindow: '12:30 PM & 6:45 PM',
      bestDays: ['Wednesday', 'Friday', 'Sunday'],
      reachBoost: '1.9x Explore Distribution',
      algorithmInsight: 'Lunchtime saves and weekend DM share velocity triggers explore carousel recommendations.',
      hashtags: ['#reelsviral', '#contentstrategy', '#growthmindset', '#videoediting'],
    },
    {
      platform: 'youtube' as const,
      name: 'YouTube Shorts',
      color: 'from-red-600 to-rose-700',
      optimalWindow: '4:00 PM - 6:30 PM',
      bestDays: ['Thursday', 'Friday', 'Saturday'],
      reachBoost: '2.1x Search & Browse Shelf Indexing',
      algorithmInsight: 'Gives the YouTube indexing pipeline 2 hours before peak evening recommendation shelves.',
      hashtags: ['#shorts', '#videotips', '#productivity', '#tech'],
    },
    {
      platform: 'x' as const,
      name: 'X (Twitter)',
      color: 'from-neutral-700 to-neutral-900',
      optimalWindow: '8:30 AM & 1:15 PM',
      bestDays: ['Monday', 'Tuesday', 'Wednesday'],
      reachBoost: '1.6x Retweet & Bookmark Multiplier',
      algorithmInsight: 'Morning commute thought leadership consumption with high reply threading.',
      hashtags: ['#BuildingInPublic', '#ArtificialIntelligence', '#Solopreneur'],
    },
  ];

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const handleGenerateHooksWithGemini = async () => {
    setIsGeneratingHooks(true);
    await new Promise((r) => setTimeout(r, 700));
    setGeneratedHooks([
      {
        type: 'Curiosity Loop',
        text: activeClip?.hook ? `${activeClip.hook} Here's what nobody tells you...` : 'Why most creators get this completely wrong...',
        strength: 97,
        predictedRetention: '86%',
      },
      {
        type: 'Bold Statement',
        text: 'Stop doing this in your videos immediately — it is killing your reach.',
        strength: 94,
        predictedRetention: '82%',
      },
      {
        type: 'Question Hook',
        text: 'Do you make this one mistake that costs you 90% of your views?',
        strength: 91,
        predictedRetention: '79%',
      },
    ]);
    setIsGeneratingHooks(false);
  };

  const loadPosts = useCallback(async () => {
    try {
      setPosts((await socialApi.listPosts()).posts);
    } catch {
      setPosts((prev) => prev ?? []);
    }
  }, []);

  // Refresh while anything is still on its way out, so statuses and links appear on their own.
  const inFlight = posts?.some((p) => p.status === 'publishing' || p.status === 'scheduled') ?? false;
  useEffect(() => {
    void loadPosts();
    if (!inFlight) return;
    const timer = window.setInterval(() => void loadPosts(), 15000);
    return () => window.clearInterval(timer);
  }, [loadPosts, inFlight]);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <PageHeader
        title="Scheduler"
        description="Pick a clip, write the caption, and publish now or at the time your audience is online."
        actions={
          <div className="flex items-center gap-2 h-9 pl-3 pr-1 rounded-xl border border-neutral-800 bg-neutral-900">
            <Globe className="w-4 h-4 text-amber-400 shrink-0" aria-hidden="true" />
            <span className="text-[11px] font-semibold text-neutral-500 hidden sm:inline">Audience time</span>
            <Select
              value={selectedTimezone}
              onChange={setSelectedTimezone}
              options={TIMEZONE_OPTIONS}
              aria-label="Audience timezone"
              className="bg-transparent text-xs font-semibold text-white focus:outline-none"
            />
          </div>
        }
      />

      <PostCalendar posts={posts} timeZone={selectedTimezone} />

      {/* Suggested posting windows per platform */}
      <section aria-labelledby="best-times" className="space-y-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="best-times" className="text-sm font-bold text-white">Suggested times</h2>
          <NotWiredBadge
            label="Sample data"
            reason="These windows, boosts and hashtags are fixed examples in the app, not calculated from your audience."
          />
          <span className="text-xs text-neutral-500">Pick a platform to get its hashtags below</span>
        </div>
        <div className="flex gap-3 overflow-x-auto pb-1 -mx-4 px-4 sm:mx-0 sm:px-0 sm:grid sm:grid-cols-2 lg:grid-cols-4 [scrollbar-width:none]" role="group" aria-label="Platform">
          {PLATFORM_TIMINGS.map((p) => {
            const isSelected = selectedPlatform === p.platform;
            return (
              <button
                key={p.platform}
                type="button"
                onClick={() => setSelectedPlatform(p.platform)}
                aria-pressed={isSelected}
                className={`shrink-0 w-[240px] sm:w-auto text-left rounded-2xl p-4 border transition-colors ${
                  isSelected ? 'bg-neutral-900 border-amber-500/50 ring-1 ring-amber-500/20' : 'bg-neutral-900/60 border-neutral-800 hover:border-neutral-700'
                }`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-white">{p.name}</span>
                  <span className="text-[10.5px] px-1.5 py-0.5 rounded-full bg-neutral-800 text-neutral-300 font-semibold">{p.reachBoost.split(' ')[0]}</span>
                </span>
                <span className="mt-2 flex items-center gap-1.5 text-amber-300 text-[13px] font-bold">
                  <Clock className="w-3.5 h-3.5" />
                  {p.optimalWindow}
                </span>
                <span className="block text-[11px] text-neutral-500 mt-0.5">{p.bestDays.join(', ')}</span>
                <span className="block text-[11.5px] text-neutral-400 mt-2 line-clamp-2">{p.algorithmInsight}</span>
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Compose */}
        <section className="lg:col-span-7 min-w-0 p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-5" aria-labelledby="compose-title">
          <h2 id="compose-title" className="text-sm font-bold text-white">New post</h2>

          <div>
            <span className="text-xs font-semibold text-neutral-300 block mb-1.5">Clip</span>
            <div className="flex items-center gap-3">
              <span className="relative w-10 aspect-[9/16] rounded-md overflow-hidden bg-neutral-800 shrink-0">
                {activeClip?.posterUrl && <img src={activeClip.posterUrl} alt="" className="absolute inset-0 w-full h-full object-cover" />}
              </span>
              <Select
                value={activeClip?.id}
                onChange={(id) => {
                  const found = clips.find((c) => c.id === id);
                  if (found) {
                    setActiveClip(found);
                    onSelectClip?.(found);
                  }
                }}
                options={clips.map((c) => ({
                  value: c.id,
                  label: `${c.title} · score ${c.viralityScore} · ${c.duration}s`,
                }))}
                placeholder={clips.length ? 'Choose a clip' : 'No clips in this project yet'}
                aria-label="Clip to schedule"
                className="flex-1 min-w-0 h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white focus:outline-none focus:border-amber-400"
              />
            </div>
          </div>

          {/* Hook ideas */}
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-neutral-300">Hook ideas</span>
              <NotWiredBadge label="Not wired" reason="Refresh returns fixed example hooks after a short wait; no AI is called yet." />
              <span className="flex-1" />
              <button
                type="button"
                onClick={handleGenerateHooksWithGemini}
                disabled={isGeneratingHooks}
                className="h-8 px-2.5 rounded-lg border border-neutral-700 text-amber-300 text-xs font-semibold hover:bg-neutral-800 flex items-center gap-1.5 disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {isGeneratingHooks ? 'Generating…' : 'Refresh ideas'}
              </button>
            </div>
            {generatedHooks.length === 0 ? (
              <p className="text-[11.5px] text-neutral-500">Tap Refresh ideas to get opening lines you can copy into the caption.</p>
            ) : (
              generatedHooks.map((h, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-neutral-950 border border-neutral-800">
                  <div className="min-w-0 flex-1 space-y-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="text-[10.5px] px-1.5 py-0.5 rounded-md font-semibold bg-violet-500/10 text-violet-300">{h.type}</span>
                      <span className="text-[11px] text-neutral-500">{h.predictedRetention} predicted retention</span>
                    </span>
                    <p className="text-[13px] text-neutral-100 leading-snug">“{h.text}”</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCustomCaption((prev) => `${h.text}\n\n${prev}`)}
                    className="h-8 px-2.5 rounded-lg border border-neutral-700 text-[11.5px] font-semibold text-white hover:bg-neutral-800 shrink-0"
                  >
                    Use
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCopy(h.text)}
                    className="h-8 w-8 flex items-center justify-center rounded-lg text-neutral-400 hover:text-white shrink-0"
                    aria-label="Copy hook"
                  >
                    {copiedText === h.text ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Caption */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label htmlFor="scheduler-caption" className="text-xs font-semibold text-neutral-300">Caption</label>
              <span className="text-[11px] text-neutral-500 tabular-nums">{customCaption.length} characters</span>
            </div>
            <textarea
              id="scheduler-caption"
              rows={4}
              value={customCaption}
              onChange={(e) => setCustomCaption(e.target.value)}
              className="w-full p-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-neutral-100 leading-relaxed focus:outline-none focus:border-amber-400 resize-y"
            />
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Add a hashtag">
              {(PLATFORM_TIMINGS.find((p) => p.platform === selectedPlatform)?.hashtags || []).map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => setCustomCaption((prev) => `${prev} ${tag}`)}
                  className="h-7 px-2.5 rounded-full bg-neutral-950 border border-neutral-800 text-[11.5px] text-amber-300 hover:border-amber-400 transition-colors flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" />
                  {tag}
                </button>
              ))}
            </div>
          </div>

          {/* Publish or schedule to connected accounts */}
          <PublishComposer clip={activeClip} baseCaption={customCaption} timeZone={selectedTimezone} onPublished={loadPosts} />
        </section>

        <div className="lg:col-span-5 min-w-0">
          <ScheduledPostsQueue posts={posts} timeZone={selectedTimezone} onChanged={loadPosts} />
        </div>
      </div>
    </div>
  );
};
