"use client";
import React, { useState, useEffect, useCallback } from 'react';
import {
  Palette,
  Sparkles,
  Type,
  Image as ImageIcon,
  Check,
  Save,
  Sliders,
  Smartphone,
  Flame,
  Zap,
  Smile,
  MessageSquare
} from 'lucide-react';
import { BrandKit } from '@/lib/types';
import { brandKitApi } from '@/lib/api';
import { CAPTION_PRESETS } from '@/lib/data/captionPresets';

const DEFAULT_BRAND_KIT: BrandKit = {
  id: '',
  brandName: '',
  logoUrl: '',
  logoPosition: 'top_right',
  logoOpacity: 0.85,
  logoSize: 28,
  primaryColor: '#f59e0b',
  secondaryColor: '#f43f5e',
  preferredFont: 'Syne',
  defaultPreset: 'hormozi',
  autoEmojis: true,
  outroCtaText: '',
  createdAt: '',
  updatedAt: '',
};

export const BrandKitView: React.FC = () => {
  const [brandKit, setBrandKit] = useState<BrandKit>(DEFAULT_BRAND_KIT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBrandKit = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await brandKitApi.getMe();
      setBrandKit({
        id: data.id,
        brandName: data.brandName,
        logoUrl: data.logoUrl || '',
        logoPosition: data.logoPosition as BrandKit['logoPosition'],
        logoOpacity: data.logoOpacity / 100,
        logoSize: data.logoSize,
        primaryColor: data.primaryColor,
        secondaryColor: data.secondaryColor,
        preferredFont: data.preferredFont,
        defaultPreset: data.defaultPreset as BrandKit['defaultPreset'],
        autoEmojis: data.autoEmojis,
        outroCtaText: data.outroCtaText,
        createdAt: data.createdAt,
        updatedAt: data.updatedAt,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load brand kit');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBrandKit();
  }, [fetchBrandKit]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        brand_name: brandKit.brandName,
        logo_url: brandKit.logoUrl || undefined,
        logo_position: brandKit.logoPosition,
        logo_opacity: Math.round(brandKit.logoOpacity * 100),
        logo_size: brandKit.logoSize,
        primary_color: brandKit.primaryColor,
        secondary_color: brandKit.secondaryColor,
        preferred_font: brandKit.preferredFont,
        default_preset: brandKit.defaultPreset,
        auto_emojis: brandKit.autoEmojis,
        outro_cta_text: brandKit.outroCtaText,
      };
      const data = await brandKitApi.create(payload);
      setBrandKit({
        id: data.id,
        brandName: data.brandName,
        logoUrl: data.logoUrl || '',
        logoPosition: data.logoPosition as BrandKit['logoPosition'],
        logoOpacity: data.logoOpacity / 100,
        logoSize: data.logoSize,
        primaryColor: data.primaryColor,
        secondaryColor: data.secondaryColor,
        preferredFont: data.preferredFont,
        defaultPreset: data.defaultPreset as BrandKit['defaultPreset'],
        autoEmojis: data.autoEmojis,
        outroCtaText: data.outroCtaText,
        createdAt: data.createdAt,
        updatedAt: data.updatedAt,
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save brand kit');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-xs text-neutral-400">Loading brand kit...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-5 lg:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Brand Identity Engine
            </span>
            <span className="text-xs text-neutral-400">
              Consistent Typography, Watermarks & Subtitle Presets
            </span>
          </div>
          <h1 className="text-xl lg:text-2xl font-extrabold text-white tracking-tight font-['Syne',sans-serif]">
            Brand Kit & Creator Presets
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Apply custom fonts, brand watermarks, and kinetic subtitle styles automatically to every generated short.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-400 hover:to-rose-400 text-neutral-950 font-bold text-xs shadow-lg shadow-rose-500/25 active:scale-95 transition-all flex items-center gap-2 shrink-0 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {savedSuccess ? <Check className="w-4 h-4 text-neutral-950" /> : <Save className="w-4 h-4" />}
          <span>{saving ? 'Saving...' : savedSuccess ? 'Brand Kit Saved!' : 'Save Brand Settings'}</span>
        </button>
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-3 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Main 2-Column Split: Controls (Left) + 9:16 Live Phone Preview (Right) */}
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Config Panels (7 cols) */}
        <div className="lg:col-span-7 space-y-5">
          {/* Panel 1: Brand Info & Logo Watermark */}
          <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
            <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-amber-400" />
              <span>Brand Logo & Watermark</span>
            </h3>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-neutral-400 block mb-1">Brand / Channel Name:</label>
                <input
                  type="text"
                  value={brandKit.brandName}
                  onChange={(e) => setBrandKit({ ...brandKit, brandName: e.target.value })}
                  className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400 font-semibold"
                />
              </div>

              <div>
                <label className="text-xs text-neutral-400 block mb-1">Watermark Position:</label>
                <select
                  value={brandKit.logoPosition}
                  onChange={(e) =>
                    setBrandKit({
                      ...brandKit,
                      logoPosition: e.target.value as BrandKit['logoPosition'],
                    })
                  }
                  className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400 font-semibold cursor-pointer"
                >
                  <option value="top_right">Top Right</option>
                  <option value="top_left">Top Left</option>
                  <option value="bottom_right">Bottom Right</option>
                  <option value="bottom_left">Bottom Left</option>
                </select>
              </div>
            </div>

            {/* Sliders: Logo Opacity and Size */}
            <div className="grid sm:grid-cols-2 gap-4 pt-2 border-t border-neutral-800">
              <div>
                <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                  <span>Watermark Opacity</span>
                  <span className="font-mono">{Math.round(brandKit.logoOpacity * 100)}%</span>
                </div>
                <input
                  type="range"
                  min={0.2}
                  max={1.0}
                  step={0.05}
                  value={brandKit.logoOpacity}
                  onChange={(e) =>
                    setBrandKit({
                      ...brandKit,
                      logoOpacity: Number(e.target.value),
                    })
                  }
                  className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                />
              </div>

              <div>
                <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                  <span>Watermark Size</span>
                  <span className="font-mono">{brandKit.logoSize}px</span>
                </div>
                <input
                  type="range"
                  min={18}
                  max={48}
                  step={2}
                  value={brandKit.logoSize}
                  onChange={(e) =>
                    setBrandKit({
                      ...brandKit,
                      logoSize: Number(e.target.value),
                    })
                  }
                  className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                />
              </div>
            </div>
          </div>

          {/* Panel 2: Subtitle Typography & Color Palette */}
          <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
            <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
              <Type className="w-4 h-4 text-rose-400" />
              <span>Typography & Highlight Colors</span>
            </h3>

            {/* Font Family Selector */}
            <div>
              <label className="text-xs text-neutral-400 block mb-1.5">Default Font Family:</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { name: 'Syne (Ultra Bold)', value: 'Syne' },
                  { name: 'Plus Jakarta Sans', value: 'Plus Jakarta Sans' },
                  { name: 'JetBrains Mono', value: 'JetBrains Mono' },
                ].map((f) => (
                  <button
                    key={f.value}
                    onClick={() => setBrandKit({ ...brandKit, preferredFont: f.value })}
                    className={`p-2.5 rounded-xl border text-xs font-bold text-center transition-all ${
                      brandKit.preferredFont === f.value
                        ? 'bg-neutral-800 border-amber-400 text-amber-300 ring-1 ring-amber-400/30'
                        : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-white'
                    }`}
                  >
                    {f.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Colors */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-neutral-400 block mb-1">Primary Highlight Color:</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={brandKit.primaryColor}
                    onChange={(e) => setBrandKit({ ...brandKit, primaryColor: e.target.value })}
                    className="w-9 h-9 rounded-lg bg-transparent cursor-pointer border border-neutral-700"
                  />
                  <input
                    type="text"
                    value={brandKit.primaryColor}
                    onChange={(e) => setBrandKit({ ...brandKit, primaryColor: e.target.value })}
                    className="flex-1 p-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs font-mono text-white uppercase"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-neutral-400 block mb-1">Secondary Accent Color:</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={brandKit.secondaryColor}
                    onChange={(e) => setBrandKit({ ...brandKit, secondaryColor: e.target.value })}
                    className="w-9 h-9 rounded-lg bg-transparent cursor-pointer border border-neutral-700"
                  />
                  <input
                    type="text"
                    value={brandKit.secondaryColor}
                    onChange={(e) => setBrandKit({ ...brandKit, secondaryColor: e.target.value })}
                    className="flex-1 p-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs font-mono text-white uppercase"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Panel 3: Default Subtitle Presets */}
          <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
            <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>Default Preset for Auto-Generation</span>
            </h3>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {CAPTION_PRESETS.map((p) => {
                const isSelected = brandKit.defaultPreset === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => setBrandKit({ ...brandKit, defaultPreset: p.id })}
                    className={`p-3 rounded-xl border text-left transition-all relative ${
                      isSelected
                        ? 'bg-neutral-800 border-amber-400 text-white ring-1 ring-amber-400/40 shadow-lg'
                        : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:border-neutral-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">{p.name}</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-semibold">
                        {p.badge}
                      </span>
                    </div>
                    <p className="text-[10px] text-neutral-500 mt-1 line-clamp-1">
                      {p.description}
                    </p>
                  </button>
                );
              })}
            </div>

            {/* Toggle: Auto Emojis & Outro CTA */}
            <div className="space-y-3 pt-3 border-t border-neutral-800">
              <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer">
                <div className="flex items-center gap-2">
                  <Smile className="w-4 h-4 text-amber-400" />
                  <div>
                    <span className="text-xs font-bold text-white block">Auto-Inject Emojis in Subtitles</span>
                    <span className="text-[10px] text-neutral-400">
                      Matches keywords like "secret", "money", "rocket" with animated stickers
                    </span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={brandKit.autoEmojis}
                  onChange={(e) => setBrandKit({ ...brandKit, autoEmojis: e.target.checked })}
                  className="w-4 h-4 rounded accent-amber-400 cursor-pointer"
                />
              </label>

              <div>
                <label className="text-xs text-neutral-400 block mb-1">
                  Default Outro Call-To-Action (CTA) Text:
                </label>
                <input
                  type="text"
                  value={brandKit.outroCtaText}
                  onChange={(e) => setBrandKit({ ...brandKit, outroCtaText: e.target.value })}
                  className="w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: 9:16 Live Phone Mockup Preview (5 cols) */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="sticky top-20 w-full max-w-xs space-y-3">
            <div className="flex items-center justify-between text-xs text-neutral-400 px-1">
              <span className="font-bold flex items-center gap-1.5">
                <Smartphone className="w-4 h-4 text-amber-400" />
                <span>Live Brand Preview</span>
              </span>
              <span className="font-mono text-emerald-400">9:16 Vertical</span>
            </div>

            {/* Phone Frame */}
            <div className="relative aspect-[9/16] w-full rounded-[36px] bg-neutral-950 border-4 border-neutral-800 overflow-hidden shadow-2xl flex flex-col justify-between p-4 ring-1 ring-white/10">
              {/* Phone Speaker Notch */}
              <div className="absolute top-2.5 left-1/2 -translate-x-1/2 w-20 h-4 bg-neutral-900 rounded-full z-30" />

              {/* Background Video Simulation */}
              <img
                src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&auto=format&fit=crop&q=80"
                alt="Brand Mockup"
                className="absolute inset-0 w-full h-full object-cover opacity-70"
              />
              <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-black/70" />

              {/* Watermark Logo Render */}
              <div
                className={`absolute z-20 ${
                  brandKit.logoPosition === 'top_right'
                    ? 'top-8 right-4'
                    : brandKit.logoPosition === 'top_left'
                    ? 'top-8 left-4'
                    : brandKit.logoPosition === 'bottom_right'
                    ? 'bottom-20 right-4'
                    : 'bottom-20 left-4'
                }`}
                style={{ opacity: brandKit.logoOpacity }}
              >
                <div className="flex items-center gap-1.5 bg-black/60 backdrop-blur-md px-2 py-1 rounded-lg border border-white/10">
                  <div
                    className="w-4 h-4 rounded-full bg-gradient-to-tr from-amber-500 to-rose-500"
                    style={{ width: `${brandKit.logoSize - 8}px`, height: `${brandKit.logoSize - 8}px` }}
                  />
                  <span className="text-[10px] font-black text-white font-['Syne',sans-serif]">
                    {brandKit.brandName || 'Your Brand'}
                  </span>
                </div>
              </div>

              {/* Subtitles Render with Selected Colors and Font */}
              <div className="relative z-20 my-auto text-center px-3 space-y-1">
                <div
                  className="inline-block px-3 py-1.5 rounded-xl bg-black/80 backdrop-blur-md shadow-2xl border border-white/10"
                  style={{ fontFamily: brandKit.preferredFont }}
                >
                  <span className="text-base font-black text-white uppercase tracking-tight">
                    THE MOST POWERFUL{' '}
                    <span
                      className="inline-block scale-110 transition-transform"
                      style={{ color: brandKit.primaryColor }}
                    >
                      PSYCHOLOGICAL 🔥
                    </span>{' '}
                    TRIGGER
                  </span>
                </div>

                <p
                  className="text-xs font-bold uppercase tracking-wide"
                  style={{ color: brandKit.secondaryColor, fontFamily: brandKit.preferredFont }}
                >
                  IN SHORT-FORM VIDEO
                </p>
              </div>

              {/* Outro CTA Bottom Banner */}
              <div className="relative z-20 text-center pb-2">
                <span className="text-[10px] font-semibold text-neutral-300 bg-neutral-900/90 px-3 py-1 rounded-full border border-neutral-700 inline-block shadow-md">
                  {brandKit.outroCtaText || 'Follow @yourbrand for daily viral breakdowns!'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
