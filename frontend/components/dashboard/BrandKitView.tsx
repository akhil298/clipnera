"use client";
import React, { useState, useEffect, useCallback } from 'react';
import { Check, Image as ImageIcon, Loader2, Save, Smartphone, Smile, Sparkles, Type } from 'lucide-react';
import { BrandKit } from '@/lib/types';
import { brandKitApi } from '@/lib/api';
import { FEATURE_LABELS, usePlan } from '@/hooks/usePlan';
import { ProLockBadge } from './ProLockBadge';
import { CaptionStylePreview } from './CaptionStylePreview';
import { BrandKitSkeleton } from '@/components/skeletons';
import { CAPTION_PRESETS } from '@/lib/data/captionPresets';
import { getCaptionConfig } from '@/lib/utils/captionStyles';
import { PageHeader } from '@/components/ui/PageHeader';

type LogoPosition = BrandKit['logoPosition'];

/** The four watermark corners, in reading order for the 2×2 picker. */
const LOGO_POSITIONS: { value: LogoPosition; label: string }[] = [
  { value: 'top_left', label: 'Top left' },
  { value: 'top_right', label: 'Top right' },
  { value: 'bottom_left', label: 'Bottom left' },
  { value: 'bottom_right', label: 'Bottom right' },
];

const FONTS = [
  { name: 'Syne', note: 'Ultra bold', value: 'Syne' },
  { name: 'Plus Jakarta Sans', note: 'Clean', value: 'Plus Jakarta Sans' },
  { name: 'JetBrains Mono', note: 'Techy', value: 'JetBrains Mono' },
];

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
  isCustomized: false,
  createdAt: '',
  updatedAt: '',
};

/** The API stores opacity as 0-100; the sliders work in 0-1. */
const fromApi = (data: BrandKit): BrandKit => ({
  ...data,
  logoUrl: data.logoUrl || '',
  logoOpacity: data.logoOpacity / 100,
});

/** The fields a user edits; compared to tell whether anything is unsaved. */
const editableSnapshot = (kit: BrandKit) =>
  JSON.stringify([
    kit.brandName, kit.logoUrl, kit.logoPosition, kit.logoOpacity, kit.logoSize, kit.primaryColor,
    kit.secondaryColor, kit.preferredFont, kit.defaultPreset, kit.autoEmojis, kit.outroCtaText,
  ]);

const fieldClass =
  'w-full h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400';

export const BrandKitView: React.FC = () => {
  const { canUse, promptUpgrade } = usePlan();
  const canEdit = canUse('brand_kit_edit');
  const [brandKit, setBrandKit] = useState<BrandKit>(DEFAULT_BRAND_KIT);
  const [savedKit, setSavedKit] = useState<BrandKit>(DEFAULT_BRAND_KIT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (changes: Partial<BrandKit>) => setBrandKit((kit) => ({ ...kit, ...changes }));

  const fetchBrandKit = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const kit = fromApi(await brandKitApi.getMe());
      setBrandKit(kit);
      setSavedKit(kit);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load brand kit');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBrandKit();
  }, [fetchBrandKit]);

  const isDirty = editableSnapshot(brandKit) !== editableSnapshot(savedKit);

  const handleSave = async () => {
    // Free plans keep their existing kit visible; saving changes is Pro.
    if (!canEdit) {
      promptUpgrade(FEATURE_LABELS.brand_kit_edit);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const data = await brandKitApi.create({
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
      });
      const kit = fromApi(data);
      setBrandKit(kit);
      setSavedKit(kit);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save brand kit');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <BrandKitSkeleton />;
  }

  const saveButton = (
    <button
      type="button"
      onClick={handleSave}
      disabled={saving || (canEdit && !isDirty)}
      className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : savedSuccess ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
      {saving ? 'Saving…' : savedSuccess ? 'Saved' : 'Save brand kit'}
      {!canEdit && <ProLockBadge feature={FEATURE_LABELS.brand_kit_edit} className="bg-neutral-950/20 text-neutral-950 ring-neutral-950/30" />}
    </button>
  );

  const logoCorner: Record<LogoPosition, string> = {
    top_right: 'top-8 right-4',
    top_left: 'top-8 left-4',
    bottom_right: 'bottom-20 right-4',
    bottom_left: 'bottom-20 left-4',
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300 pb-20">
      <PageHeader
        title="Brand kit"
        description="Applied to every new clip: watermark, fonts, colors and the default caption style."
        actions={saveButton}
      />

      {error && (
        <div role="alert" className="rounded-xl bg-rose-500/10 border border-rose-500/30 px-3.5 py-2.5 text-xs text-rose-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 min-w-0 space-y-5">
          {/* Identity and watermark */}
          <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-5" aria-labelledby="brand-identity">
            <h2 id="brand-identity" className="text-sm font-bold text-white flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-amber-400" /> Identity and watermark
            </h2>

            <div>
              <label htmlFor="brand-name" className="text-xs font-semibold text-neutral-300 block mb-1.5">Brand or channel name</label>
              <input id="brand-name" type="text" value={brandKit.brandName} placeholder="e.g. Clipnera"
                onChange={(e) => update({ brandName: e.target.value })} className={fieldClass} />
            </div>

            <div className="flex flex-col sm:flex-row gap-5">
              <div>
                <span className="text-xs font-semibold text-neutral-300 block mb-1.5">Position</span>
                <div className="grid grid-cols-2 gap-1.5 p-1.5 w-[132px] aspect-[9/12] rounded-xl bg-neutral-950 border border-neutral-800" role="radiogroup" aria-label="Watermark position">
                  {LOGO_POSITIONS.map((pos) => {
                    const selected = brandKit.logoPosition === pos.value;
                    return (
                      <button key={pos.value} type="button" role="radio" aria-checked={selected} aria-label={pos.label} title={pos.label}
                        onClick={() => update({ logoPosition: pos.value })}
                        className={`rounded-lg flex p-1.5 transition-colors ${pos.value.startsWith('top') ? 'items-start' : 'items-end'} ${pos.value.endsWith('left') ? 'justify-start' : 'justify-end'} ${
                          selected ? 'bg-amber-500/15 ring-1 ring-amber-400' : 'bg-neutral-900 hover:bg-neutral-800'
                        }`}>
                        <span className={`w-3.5 h-3.5 rounded ${selected ? 'bg-amber-400' : 'bg-neutral-600'}`} />
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex-1 space-y-5">
                <div>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <label htmlFor="logo-opacity" className="font-semibold text-neutral-300">Opacity</label>
                    <span className="text-neutral-400 tabular-nums">{Math.round(brandKit.logoOpacity * 100)}%</span>
                  </div>
                  <input id="logo-opacity" type="range" min={0.2} max={1.0} step={0.05} value={brandKit.logoOpacity}
                    onChange={(e) => update({ logoOpacity: Number(e.target.value) })}
                    className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400" />
                </div>
                <div>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <label htmlFor="logo-size" className="font-semibold text-neutral-300">Size</label>
                    <span className="text-neutral-400 tabular-nums">{brandKit.logoSize} px</span>
                  </div>
                  <input id="logo-size" type="range" min={18} max={48} step={2} value={brandKit.logoSize}
                    onChange={(e) => update({ logoSize: Number(e.target.value) })}
                    className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400" />
                </div>
              </div>
            </div>
          </section>

          {/* Type and color */}
          <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-5" aria-labelledby="brand-type">
            <h2 id="brand-type" className="text-sm font-bold text-white flex items-center gap-2">
              <Type className="w-4 h-4 text-amber-400" /> Type and color
            </h2>

            <div>
              <span className="text-xs font-semibold text-neutral-300 block mb-1.5">Font</span>
              <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Font">
                {FONTS.map((f) => {
                  const selected = brandKit.preferredFont === f.value;
                  return (
                    <button key={f.value} type="button" role="radio" aria-checked={selected}
                      onClick={() => update({ preferredFont: f.value })}
                      className={`p-3 rounded-xl border text-left transition-colors ${
                        selected ? 'bg-amber-500/10 border-amber-400 ring-1 ring-amber-400/30' : 'bg-neutral-950 border-neutral-800 hover:border-neutral-700'
                      }`}>
                      <span className="block text-2xl text-white leading-none" style={{ fontFamily: f.value, fontWeight: 800 }}>Aa</span>
                      <span className="block mt-2 text-[11.5px] font-semibold text-neutral-200 truncate">{f.name}</span>
                      <span className="block text-[10.5px] text-neutral-500">{f.note}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              {([
                ['primaryColor', 'Highlight color', 'The active word in captions'],
                ['secondaryColor', 'Accent color', 'Supporting text and details'],
              ] as const).map(([key, name, hint]) => (
                <div key={key}>
                  <label htmlFor={`brand-${key}`} className="text-xs font-semibold text-neutral-300 block mb-1.5">{name}</label>
                  <div className="flex items-center gap-2">
                    <input type="color" value={brandKit[key]} onChange={(e) => update({ [key]: e.target.value })}
                      aria-label={`${name} picker`}
                      className="w-10 h-10 rounded-xl bg-transparent cursor-pointer border border-neutral-700 shrink-0" />
                    <input id={`brand-${key}`} type="text" value={brandKit[key]} onChange={(e) => update({ [key]: e.target.value })}
                      className={`${fieldClass} font-mono uppercase`} />
                  </div>
                  <p className="text-[11px] text-neutral-500 mt-1">{hint}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Default caption style */}
          <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-4" aria-labelledby="brand-preset">
            <div className="flex items-center gap-2">
              <h2 id="brand-preset" className="text-sm font-bold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" /> Default caption style
              </h2>
              <span className="text-xs text-neutral-500">{CAPTION_PRESETS.length} styles</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 max-h-[26rem] overflow-y-auto pr-1 caption-preset-scroll" role="radiogroup" aria-label="Default caption style">
              {CAPTION_PRESETS.map((p) => {
                const isSelected = brandKit.defaultPreset === p.id;
                return (
                  <button key={p.id} type="button" role="radio" aria-checked={isSelected}
                    onClick={() => update({ defaultPreset: p.id })}
                    className={`rounded-xl border text-left overflow-hidden transition-colors ${
                      isSelected ? 'border-amber-400 ring-1 ring-amber-400/40 bg-neutral-800' : 'border-neutral-800 bg-neutral-950 hover:border-neutral-700'
                    }`}>
                    <CaptionStylePreview config={getCaptionConfig(p.id)} className="h-14 w-full !rounded-none" />
                    <span className="flex items-center justify-between gap-1 px-2.5 pt-2">
                      <span className="text-xs font-semibold text-white truncate">{p.name}</span>
                      {isSelected ? <Check className="w-3.5 h-3.5 text-amber-400 shrink-0" /> : (
                        <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400 font-semibold shrink-0">{p.badge}</span>
                      )}
                    </span>
                    <span className="block px-2.5 pb-2.5 pt-0.5 text-[10.5px] text-neutral-500 line-clamp-1">{p.description}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Extras */}
          <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-4" aria-labelledby="brand-extras">
            <h2 id="brand-extras" className="text-sm font-bold text-white flex items-center gap-2">
              <Smile className="w-4 h-4 text-amber-400" /> Extras
            </h2>
            <label className="flex items-center justify-between gap-4 p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer">
              <span>
                <span className="text-[13px] font-semibold text-white block">Auto emojis in captions</span>
                <span className="text-[11.5px] text-neutral-500">Adds a matching emoji to words like “secret”, “money” or “rocket”</span>
              </span>
              <input type="checkbox" checked={brandKit.autoEmojis} onChange={(e) => update({ autoEmojis: e.target.checked })}
                className="w-4 h-4 rounded accent-amber-400 cursor-pointer shrink-0" />
            </label>
            <div>
              <label htmlFor="brand-cta" className="text-xs font-semibold text-neutral-300 block mb-1.5">End card call to action</label>
              <input id="brand-cta" type="text" value={brandKit.outroCtaText} placeholder="e.g. Follow @yourbrand for daily breakdowns"
                onChange={(e) => update({ outroCtaText: e.target.value })} className={fieldClass} />
            </div>
          </section>
        </div>

        {/* Live preview */}
        <div className="lg:col-span-5 min-w-0 flex flex-col items-center">
          <div className="lg:sticky lg:top-20 w-full max-w-xs space-y-3">
            <div className="flex items-center justify-between text-xs text-neutral-400 px-1">
              <span className="font-semibold flex items-center gap-1.5">
                <Smartphone className="w-4 h-4 text-amber-400" /> Preview
              </span>
              <span>9:16 · {CAPTION_PRESETS.find((p) => p.id === brandKit.defaultPreset)?.name}</span>
            </div>

            <div className="relative aspect-[9/16] w-full rounded-[32px] border-[6px] border-neutral-800 overflow-hidden shadow-2xl flex flex-col justify-between p-4 bg-[radial-gradient(60%_40%_at_50%_35%,#3f2a12,transparent),linear-gradient(160deg,#1f1a2e,#0b0b0d_60%,#2a1508)]">
              <div className="absolute top-2 left-1/2 -translate-x-1/2 w-16 h-4 bg-neutral-950 rounded-full z-30" aria-hidden="true" />
              {/* A stand-in speaker, so captions read over something footage-like. */}
              <div className="absolute left-1/2 top-[30%] -translate-x-1/2 w-[46%] aspect-square rounded-full bg-black/25" aria-hidden="true" />
              <div className="absolute left-1/2 top-[52%] -translate-x-1/2 w-[62%] h-[45%] rounded-t-[45%] bg-black/25" aria-hidden="true" />

              <div className={`absolute z-20 ${logoCorner[brandKit.logoPosition]}`} style={{ opacity: brandKit.logoOpacity }}>
                <div className="flex items-center gap-1.5 bg-black/60 backdrop-blur-md px-2 py-1 rounded-lg border border-white/10">
                  {brandKit.logoUrl ? (
                    <img src={brandKit.logoUrl} alt="" className="rounded object-contain"
                      style={{ width: `${brandKit.logoSize - 8}px`, height: `${brandKit.logoSize - 8}px` }} />
                  ) : (
                    <div className="rounded-full" style={{ width: `${brandKit.logoSize - 8}px`, height: `${brandKit.logoSize - 8}px`, background: `linear-gradient(135deg, ${brandKit.primaryColor}, ${brandKit.secondaryColor})` }} />
                  )}
                  <span className="text-[10px] font-extrabold text-white" style={{ fontFamily: brandKit.preferredFont }}>
                    {brandKit.brandName || 'Your brand'}
                  </span>
                </div>
              </div>

              <div className="relative z-20 my-auto text-center px-2 space-y-1">
                <div className="inline-block px-3 py-1.5 rounded-xl bg-black/75 backdrop-blur-md border border-white/10" style={{ fontFamily: brandKit.preferredFont }}>
                  <span className="text-base font-black text-white uppercase tracking-tight">
                    The most powerful <span style={{ color: brandKit.primaryColor }}>trigger{brandKit.autoEmojis ? ' 🔥' : ''}</span>
                  </span>
                </div>
                <p className="text-xs font-bold uppercase tracking-wide" style={{ color: brandKit.secondaryColor, fontFamily: brandKit.preferredFont }}>
                  in short-form video
                </p>
              </div>

              <div className="relative z-20 text-center pb-1">
                <span className="text-[10px] font-semibold text-neutral-200 bg-neutral-900/90 px-3 py-1 rounded-full border border-neutral-700 inline-block">
                  {brandKit.outroCtaText || 'Follow @yourbrand for daily breakdowns'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Unsaved changes */}
      {isDirty && (
        <div role="status" className="fixed z-30 inset-x-3 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] md:bottom-5 md:left-auto md:right-6 md:w-auto flex items-center gap-3 rounded-2xl border border-neutral-700 bg-neutral-900/95 backdrop-blur px-4 py-3 shadow-2xl shadow-black/60 animate-in slide-in-from-bottom-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" aria-hidden="true" />
          <span className="text-[13px] font-semibold text-white">Unsaved changes</span>
          <span className="flex-1" />
          <button type="button" onClick={() => setBrandKit(savedKit)} className="h-8 px-3 rounded-lg text-xs font-semibold text-neutral-300 hover:bg-neutral-800">
            Discard
          </button>
          {saveButton}
        </div>
      )}
    </div>
  );
};
