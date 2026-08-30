"use client";
import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  Flame,
  Eye,
  Share2,
  ThumbsUp,
  Clock,
  Zap,
  ArrowUpRight,
  Sparkles,
  Smartphone,
  Layers,
  Award,
  Search,
  Filter
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import { RETENTION_CURVE_DATA } from '@/lib/data/mockProjects';

export const ViralAnalyticsView: React.FC = () => {
  const [activePlatformFilter, setActivePlatformFilter] = useState<'all' | 'tiktok' | 'reels' | 'shorts'>('all');
  const [simulatorHook, setSimulatorHook] = useState(
    'Why 99% of people are completely wrong about video editing in 2026'
  );
  const [simulatorResult, setSimulatorResult] = useState<{
    score: number;
    retentionLift: string;
    verdict: string;
    keyTriggers: string[];
  } | null>({
    score: 96,
    retentionLift: '+44% above niche baseline',
    verdict: 'High Curiosity Gap & Loss Aversion trigger detected.',
    keyTriggers: ['Statistic Challenge', 'Future Timestamp (2026)', 'Contrarian Stance'],
  });

  const [isSimulating, setIsSimulating] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Platform Performance dataset
  const PLATFORM_PERFORMANCE = [
    { platform: 'TikTok', views: 840000, completionRate: 78, shares: 34200, retentionAvg: '82%' },
    { platform: 'IG Reels', views: 520000, completionRate: 71, shares: 18900, retentionAvg: '76%' },
    { platform: 'YT Shorts', views: 960000, completionRate: 84, shares: 41000, retentionAvg: '86%' },
    { platform: 'X / LinkedIn', views: 210000, completionRate: 64, shares: 9400, retentionAvg: '68%' },
  ];

  const handleRunSimulator = () => {
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);
      const calculatedScore = Math.floor(88 + Math.random() * 11);
      setSimulatorResult({
        score: calculatedScore,
        retentionLift: `+${calculatedScore - 52}% above niche baseline`,
        verdict:
          calculatedScore >= 94
            ? 'Exceptional hook tension. Direct psychological hook triggers rapid scroll-stop.'
            : 'Solid hook structure. Consider adding an alarmist trigger or bold number for +8% lift.',
        keyTriggers: ['Attention Stoppage', 'Kinetic Caption Fit', 'High Comment Provocation'],
      });
    }, 600);
  };

  const formatNumber = (num: number) => num.toLocaleString('en-US');

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Header */}
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-5 lg:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Cross-Platform Analytics
            </span>
            <span className="text-xs text-neutral-400">
              Real-Time Virality Telemetry & Retention Science
            </span>
          </div>
          <h1 className="text-xl lg:text-2xl font-extrabold text-white tracking-tight font-['Syne',sans-serif]">
            Viral Performance Dashboard
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Tracking 2.53M+ views generated across TikTok, Instagram Reels, and YouTube Shorts.
          </p>
        </div>

        {/* Quick Highlights Summary */}
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-neutral-950 border border-neutral-800 text-right">
            <span className="text-[10px] text-neutral-500 block uppercase font-bold">
              Avg Watchtime Lift
            </span>
            <span className="text-base font-extrabold text-emerald-400 font-mono">
              +285% vs Raw
            </span>
          </div>
        </div>
      </div>

      {/* 4 Big KPI Metric Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-2">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-semibold">Total Short-Form Views</span>
            <Eye className="w-4 h-4 text-sky-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white font-mono">2,530,000</span>
            <span className="text-xs font-bold text-emerald-400 flex items-center">
              <ArrowUpRight className="w-3 h-3" /> +34.2%
            </span>
          </div>
          <p className="text-[11px] text-neutral-500">Across 24 published clips</p>
        </div>

        <div className="p-4 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-2">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-semibold">Avg Completion Rate</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white font-mono">79.4%</span>
            <span className="text-xs font-bold text-emerald-400 flex items-center">
              <ArrowUpRight className="w-3 h-3" /> +48%
            </span>
          </div>
          <p className="text-[11px] text-neutral-500">Industry avg: 22-30%</p>
        </div>

        <div className="p-4 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-2">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-semibold">Total Shares & Saves</span>
            <Share2 className="w-4 h-4 text-rose-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white font-mono">103,500</span>
            <span className="text-xs font-bold text-rose-400 flex items-center">
              <ArrowUpRight className="w-3 h-3" /> 4.1% Rate
            </span>
          </div>
          <p className="text-[11px] text-neutral-500">Primary viral distribution engine</p>
        </div>

        <div className="p-4 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-2">
          <div className="flex items-center justify-between text-neutral-400">
            <span className="text-xs font-semibold">Avg Virality Index</span>
            <Flame className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white font-mono">94.8 / 100</span>
            <span className="text-xs font-bold text-amber-400">Top 1%</span>
          </div>
          <p className="text-[11px] text-neutral-500">Clipnera AI Quality Rating</p>
        </div>
      </div>

      {/* CORE RETENTION RETENTION COMPARISON GRAPH */}
      <div className="p-5 lg:p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-amber-400" />
              <h3 className="text-sm lg:text-base font-bold text-white font-['Syne',sans-serif]">
                Audience Retention Curve: Raw Video vs. Clipnera AI Enhanced Clip
              </h3>
            </div>
            <p className="text-xs text-neutral-400 mt-0.5">
              Notice how kinetic subtitles, B-roll overlays, and 3s auto-zooms eliminate the standard 5s drop-off cliff!
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-semibold">
            <div className="flex items-center gap-1.5 text-amber-400">
              <span className="w-3 h-3 rounded-full bg-amber-400" />
              <span>Clipnera AI Clip (74% 30s Retention)</span>
            </div>
            <div className="flex items-center gap-1.5 text-neutral-500">
              <span className="w-3 h-3 rounded-full bg-neutral-600" />
              <span>Raw Unedited Video (19%)</span>
            </div>
          </div>
        </div>

        {/* Retention Area Chart */}
        {isMounted ? (
          <div className="h-72 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={RETENTION_CURVE_DATA}>
                <defs>
                  <linearGradient id="clipneraGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="rawGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#64748b" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#64748b" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis
                  dataKey="second"
                  stroke="#737373"
                  tickFormatter={(sec) => `${sec}s`}
                  fontSize={12}
                />
                <YAxis
                  stroke="#737373"
                  tickFormatter={(val) => `${val}%`}
                  fontSize={12}
                  domain={[0, 100]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#171717',
                    border: '1px solid #404040',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                  formatter={(value: any, name: any) => [
                    `${value}% Retention`,
                    name === 'clipneraAiRetention' || name === 'opusAiRetention' ? 'Clipnera AI Enhanced' : 'Raw Video',
                  ]}
                  labelFormatter={(label) => `Timestamp: 00:${label}s`}
                />
                <Area
                  type="monotone"
                  dataKey="clipneraAiRetention"
                  stroke="#f59e0b"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#clipneraGradient)"
                  name="clipneraAiRetention"
                />
                <Area
                  type="monotone"
                  dataKey="rawRetention"
                  stroke="#64748b"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  fillOpacity={1}
                  fill="url(#rawGradient)"
                  name="rawRetention"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-72 w-full pt-4 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Grid: Platform Breakdown (Left) + AI Virality Hook Predictor Simulator (Right) */}
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        {/* Left: Platform Distribution Bars (6 cols) */}
        <div className="lg:col-span-6 p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
              <Smartphone className="w-4 h-4 text-sky-400" />
              <span>Multi-Channel Performance Breakdown</span>
            </h3>
          </div>

          <div className="space-y-3">
            {PLATFORM_PERFORMANCE.map((p, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{p.platform}</span>
                  <span className="text-xs font-mono font-bold text-emerald-400">
                    {formatNumber(p.views)} Views
                  </span>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-neutral-400">
                    <span>Completion Rate</span>
                    <span className="font-mono text-neutral-200">{p.completionRate}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-amber-500 to-rose-500"
                      style={{ width: `${p.completionRate}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-neutral-500 font-mono pt-1">
                  <span>Shares: {formatNumber(p.shares)}</span>
                  <span>Avg Retention: {p.retentionAvg}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: AI Virality Score Predictor & Simulator (6 cols) */}
        <div className="lg:col-span-6 p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                AI Virality Predictor & Hook Tester
              </h3>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-400/10 text-amber-300 font-bold font-mono">
              Clipnera AI Engine 2026
            </span>
          </div>

          <p className="text-xs text-neutral-400">
            Test any video title, hook, or concept before recording to get an instant AI Virality Score & Retention estimate.
          </p>

          <div className="space-y-2">
            <textarea
              rows={3}
              value={simulatorHook}
              onChange={(e) => setSimulatorHook(e.target.value)}
              placeholder="Type your video hook or title..."
              className="w-full p-3 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder-neutral-600 focus:outline-none focus:border-amber-400 resize-none font-medium"
            />

            <button
              onClick={handleRunSimulator}
              disabled={isSimulating}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-400 hover:to-rose-400 text-neutral-950 text-xs font-bold shadow-md shadow-rose-500/20 active:scale-95 transition-all flex items-center justify-center gap-2"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>{isSimulating ? 'Simulating Algorithm Reaction...' : 'Predict Virality Score'}</span>
            </button>
          </div>

          {/* Simulator Result Output */}
          {simulatorResult && (
            <div className="p-4 rounded-xl bg-neutral-950 border border-amber-500/30 space-y-3 animate-in fade-in">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-neutral-300">
                  Predicted Virality Score:
                </span>
                <span className="text-xl font-black text-amber-400 font-mono">
                  {simulatorResult.score} / 100
                </span>
              </div>

              <p className="text-xs text-neutral-300 font-medium">
                {simulatorResult.verdict}
              </p>

              <div className="flex flex-wrap gap-1.5 pt-1">
                {simulatorResult.keyTriggers.map((trig, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded-md bg-neutral-900 border border-neutral-800 text-[10px] text-amber-300 font-semibold"
                  >
                    ✓ {trig}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
