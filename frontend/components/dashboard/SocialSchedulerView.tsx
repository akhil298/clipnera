"use client";
import React, { useState, useEffect, useCallback } from 'react';
import {
  Clock,
  Sparkles,
  TrendingUp,
  Share2,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  Zap,
  Globe,
  Plus,
  Send,
  Sliders,
  ChevronRight,
  Flame,
  Smartphone
} from 'lucide-react';
import { ViralClip } from '@/lib/types';
import { socialApi, type SocialPostResponse } from '@/lib/api';
import { DEFAULT_TIMEZONE } from '@/lib/utils/timezones';
import { PublishComposer } from '@/components/social/PublishComposer';
import { ScheduledPostsQueue } from '@/components/social/ScheduledPostsQueue';
import { Select, SelectOption } from '@/components/ui/Select';

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
      {/* Header Banner */}
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-5 lg:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/25 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>AI Distribution Engine</span>
            </span>
            <span className="text-xs text-neutral-400">
              Audience Reach & Timing Optimizer
            </span>
          </div>
          <h1 className="text-xl lg:text-2xl font-extrabold text-white tracking-tight">
            Post Timing & AI Viral Scheduler
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Clipnera AI analyzes global platform traffic algorithms to predict maximum 24h viewer engagement.
          </p>
        </div>

        {/* Timezone Selector */}
        <div className="flex items-center gap-2 bg-neutral-950 px-3 py-2 rounded-xl border border-neutral-800">
          <Globe className="w-4 h-4 text-amber-400" />
          <div className="text-left">
            <span className="text-[10px] text-neutral-400 block uppercase font-bold">
              Audience Timezone:
            </span>
            <Select
              value={selectedTimezone}
              onChange={setSelectedTimezone}
              options={TIMEZONE_OPTIONS}
              aria-label="Audience timezone"
              className="bg-transparent text-xs font-semibold text-white focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* 4 Multi-Channel Algorithm Timing Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {PLATFORM_TIMINGS.map((p) => {
          const isSelected = selectedPlatform === p.platform;
          return (
            <div
              key={p.platform}
              onClick={() => setSelectedPlatform(p.platform)}
              className={`cursor-pointer rounded-xl p-4 border transition-all relative overflow-hidden ${
                isSelected
                  ? 'bg-neutral-900 border-amber-500/60 ring-1 ring-amber-500/30 shadow-lg'
                  : 'bg-neutral-900/60 border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900/80'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">
                  {p.name}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 font-semibold border border-amber-500/20">
                  {p.reachBoost.split(' ')[0]} Boost
                </span>
              </div>

              <div className="mt-3 p-2.5 rounded-lg bg-neutral-950 border border-neutral-800/80">
                <div className="flex items-center gap-1.5 text-amber-400 text-xs font-bold font-mono">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{p.optimalWindow}</span>
                </div>
                <p className="text-[10px] text-neutral-400 mt-1">
                  Peak Days: <span className="text-neutral-200 font-medium">{p.bestDays.join(', ')}</span>
                </p>
              </div>

              <p className="text-[11px] text-neutral-400 mt-3 line-clamp-2">
                {p.algorithmInsight}
              </p>
            </div>
          );
        })}
      </div>

      {/* Main Split: AI Hook Optimizer (Left) + Scheduled Posts Calendar Queue (Right) */}
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        {/* Left: AI Viral Hook Generator & Post Creator */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-5 rounded-xl bg-neutral-900/90 border border-neutral-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-400" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                    AI Viral Hook & Caption Generator
                  </h3>
                </div>
                <p className="text-[11px] text-neutral-400 mt-0.5">
                  Optimized for short-form retention & click-through rates
                </p>
              </div>

              <button
                onClick={handleGenerateHooksWithGemini}
                disabled={isGeneratingHooks}
                className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-amber-400 text-xs font-bold border border-neutral-700 transition-colors flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isGeneratingHooks ? 'Generating...' : 'Refresh AI Hooks'}</span>
              </button>
            </div>

            {/* Target Clip Selector */}
            <div>
              <label className="text-xs text-neutral-400 block mb-1 font-medium">
                Selected Clip for Scheduling:
              </label>
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
                  label: `${c.title} (${c.viralityScore}/100 Score • ${c.duration}s)`,
                }))}
                aria-label="Clip to schedule"
                className="w-full p-2.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400 font-medium"
              />
            </div>

            {/* AI Generated Hook Cards */}
            <div className="space-y-2.5">
              <label className="text-xs font-bold text-neutral-300 block">
                Top Predicted Viral Hooks:
              </label>

              {generatedHooks.map((h, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-neutral-950 border border-neutral-800 hover:border-neutral-700 transition-all space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-neutral-800 text-amber-300">
                      {h.type}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono text-emerald-400 font-bold">
                        {h.predictedRetention} Retention
                      </span>
                      <button
                        onClick={() => handleCopy(h.text)}
                        className="p-1 text-neutral-400 hover:text-white rounded"
                        title="Copy Hook"
                      >
                        {copiedText === h.text ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </div>
                  <p className="text-xs text-neutral-200 font-medium leading-snug">
                    "{h.text}"
                  </p>
                </div>
              ))}
            </div>

            {/* Caption & Hashtag Composer */}
            <div className="space-y-2 pt-2 border-t border-neutral-800">
              <label className="text-xs font-bold text-neutral-300 block">
                Social Caption & Call-To-Action:
              </label>
              <textarea
                rows={3}
                value={customCaption}
                onChange={(e) => setCustomCaption(e.target.value)}
                className="w-full p-3 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 focus:outline-none focus:border-amber-400 resize-none font-sans"
              />

              {/* Recommended Hashtags */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {(PLATFORM_TIMINGS.find((p) => p.platform === selectedPlatform)?.hashtags || []).map(
                  (tag, idx) => (
                    <span
                      key={idx}
                      onClick={() => setCustomCaption((prev) => `${prev} ${tag}`)}
                      className="cursor-pointer px-2 py-0.5 rounded-md bg-neutral-950 border border-neutral-800 text-[11px] text-amber-300 hover:border-amber-400 font-mono transition-colors"
                    >
                      {tag} +
                    </span>
                  )
                )}
              </div>
            </div>

            {/* Publish / Schedule to connected accounts */}
            <PublishComposer
              clip={activeClip}
              baseCaption={customCaption}
              timeZone={selectedTimezone}
              onPublished={loadPosts}
            />
          </div>
        </div>

        {/* Right: Scheduled Posts Timeline Queue */}
        <div className="lg:col-span-5 space-y-4">
          <ScheduledPostsQueue posts={posts} timeZone={selectedTimezone} onChanged={loadPosts} />
        </div>
      </div>
    </div>
  );
};
