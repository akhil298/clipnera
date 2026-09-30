"use client";
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Clapperboard, ImagePlus, Loader2, RefreshCw, Trash2, Wand2 } from 'lucide-react';
import {
  creatorIntroApi,
  INTRO_AVATAR_TYPES,
  type CreatorIntro,
  type CreatorIntroSaveRequest,
  type IntroAvatarType,
  type IntroPlatform,
  type IntroRendition,
  type IntroTheme,
} from '@/lib/api';
import { FEATURE_LABELS, usePlan } from '@/hooks/usePlan';
import { ProLockBadge } from './ProLockBadge';

/** The id the upload nudge links to (/dashboard/brand-kit#channel-intro). */
export const CHANNEL_INTRO_ANCHOR = 'channel-intro';

// Each platform's own button colour, as the intro draws it (backend creator_intro/platforms.py).
const PLATFORMS: { value: IntroPlatform; label: string; color: string }[] = [
  { value: 'youtube', label: 'YouTube', color: '#FF0000' },
  { value: 'tiktok', label: 'TikTok', color: '#FE2C55' },
  { value: 'instagram', label: 'Instagram', color: '#0095F6' },
  { value: 'twitch', label: 'Twitch', color: '#9146FF' },
  { value: 'x', label: 'X', color: '#E7E9EA' },
  { value: 'facebook', label: 'Facebook', color: '#0866FF' },
  { value: 'kick', label: 'Kick', color: '#53FC18' },
  { value: 'linkedin', label: 'LinkedIn', color: '#0A66C2' },
  { value: 'other', label: 'Other', color: '#F59E0B' },
];

const NICHES = ['Gaming', 'Travel', 'Tech', 'Education', 'Food', 'Fitness', 'Music', 'Podcast', 'Finance', 'Comedy', 'Beauty', 'Vlogs'];

const THEMES: { value: IntroTheme; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

const RENDITIONS: { value: IntroRendition; label: string; aspect: string }[] = [
  { value: '9x16', label: '9:16', aspect: 'aspect-[9/16] max-w-[240px]' },
  { value: '16x9', label: '16:9', aspect: 'aspect-video' },
  { value: '1x1', label: '1:1', aspect: 'aspect-square max-w-[320px]' },
];

const POLL_MS = 3000;

type Form = Omit<CreatorIntroSaveRequest, 'avatar_key' | 'remove_avatar'>;

const toForm = (intro: CreatorIntro | null, fallbackName: string): Form => ({
  platform: intro?.platform ?? 'youtube',
  niche: intro?.niche ?? '',
  channel_name: intro?.channel_name ?? fallbackName,
  handle: intro?.handle ?? '',
  about: intro?.about ?? '',
  tagline: intro?.tagline ?? '',
  theme: intro?.theme ?? 'auto',
  enabled: intro?.enabled ?? true,
});

const fieldClass =
  'w-full h-10 px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-400';
const labelClass = 'text-xs font-semibold text-neutral-300 block mb-1.5';

interface ChannelIntroPanelProps {
  /** Pre-fills the channel name from the brand kit before an intro exists. */
  brandName: string;
}

/**
 * The creator's own intro: made once, then played before every clip they export.
 * Pro only; Free sees the form with the lock, as with brand kit editing.
 */
export const ChannelIntroPanel: React.FC<ChannelIntroPanelProps> = ({ brandName }) => {
  const { canUse, promptUpgrade } = usePlan();
  const allowed = canUse('creator_intro');
  const [intro, setIntro] = useState<CreatorIntro | null>(null);
  const [form, setForm] = useState<Form>(() => toForm(null, brandName));
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [removeAvatar, setRemoveAvatar] = useState(false);
  const [rendition, setRendition] = useState<IntroRendition>('16x9');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await creatorIntroApi.get();
      setIntro(data);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your channel intro');
      return null;
    }
  }, []);

  useEffect(() => {
    void load().then((data) => setForm(toForm(data, brandName)));
    // brandName only seeds a new intro; later edits to the kit must not overwrite the form.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  // Arriving from the upload nudge scrolls straight here.
  useEffect(() => {
    if (window.location.hash === `#${CHANNEL_INTRO_ANCHOR}`) sectionRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Follow a render until it lands; the AI's line then shows in the form.
  useEffect(() => {
    if (intro?.status !== 'rendering') return;
    const timer = window.setInterval(async () => {
      const data = await load();
      if (data && data.status !== 'rendering') setForm((f) => ({ ...f, tagline: data.tagline ?? '' }));
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [intro?.status, load]);

  useEffect(() => () => {
    if (avatarPreview) URL.revokeObjectURL(avatarPreview);
  }, [avatarPreview]);

  const update = (changes: Partial<Form>) => setForm((f) => ({ ...f, ...changes }));

  const pickAvatar = (file: File | undefined) => {
    if (!file) return;
    if (!INTRO_AVATAR_TYPES.includes(file.type as IntroAvatarType)) {
      setError('Use a JPG, PNG or WebP picture.');
      return;
    }
    setError(null);
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
    setRemoveAvatar(false);
  };

  const createIntro = async () => {
    if (!allowed) {
      promptUpgrade(FEATURE_LABELS.creator_intro);
      return;
    }
    if (!form.channel_name.trim()) {
      setError('Add your channel name.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const avatarKey = avatarFile ? await creatorIntroApi.uploadAvatar(avatarFile) : undefined;
      await creatorIntroApi.save({ ...form, avatar_key: avatarKey, remove_avatar: removeAvatar });
      setAvatarFile(null);
      setIntro(await creatorIntroApi.render());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the intro');
    } finally {
      setBusy(false);
    }
  };

  const toggleEnabled = async () => {
    if (!intro || !allowed) return;
    const enabled = !form.enabled;
    update({ enabled });
    try {
      setIntro(await creatorIntroApi.save({ ...toForm(intro, brandName), enabled }));
    } catch (err) {
      update({ enabled: !enabled });
      setError(err instanceof Error ? err.message : 'Could not update the intro');
    }
  };

  const rendering = intro?.status === 'rendering';
  const shownAvatar = removeAvatar ? null : avatarPreview ?? intro?.avatar_url ?? null;
  const previewUrl = intro?.preview_urls[rendition];
  const selectedRendition = RENDITIONS.find((r) => r.value === rendition)!;

  return (
    <section
      id={CHANNEL_INTRO_ANCHOR}
      ref={sectionRef}
      className="scroll-mt-20 p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-5"
      aria-labelledby="channel-intro-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="channel-intro-title" className="text-sm font-bold text-white flex items-center gap-2">
            <Clapperboard className="w-4 h-4 text-amber-400" /> Channel intro
            {!allowed && <ProLockBadge feature={FEATURE_LABELS.creator_intro} />}
          </h2>
          <p className="text-xs text-neutral-400 mt-1 max-w-xl">
            A 6-second intro with your name, what your channel is about, and a cursor tapping your platform’s
            Like and Subscribe or Follow. Made once, then played before every clip you export.
          </p>
        </div>
        {intro && (
          <label className="flex items-center gap-2.5 text-xs font-semibold text-neutral-300 cursor-pointer">
            Play before every export
            <input type="checkbox" checked={form.enabled} onChange={toggleEnabled} disabled={!allowed || rendering}
              className="w-4 h-4 rounded accent-amber-400 cursor-pointer" />
          </label>
        )}
      </div>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-xl bg-rose-500/10 border border-rose-500/30 px-3.5 py-2.5 text-xs text-rose-200">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 min-w-0 space-y-4">
          <div>
            <span className={labelClass}>Platform</span>
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Platform">
              {PLATFORMS.map((p) => {
                const selected = form.platform === p.value;
                return (
                  <button key={p.value} type="button" role="radio" aria-checked={selected} onClick={() => update({ platform: p.value })}
                    className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-lg border text-xs font-semibold transition-colors ${
                      selected ? 'bg-amber-500/10 border-amber-400 text-white' : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-white'
                    }`}>
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: p.color }} aria-hidden />
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="intro-name" className={labelClass}>Channel name</label>
              <input id="intro-name" type="text" maxLength={120} value={form.channel_name} placeholder="e.g. Sreekanth Go"
                onChange={(e) => update({ channel_name: e.target.value })} className={fieldClass} />
            </div>
            <div>
              <label htmlFor="intro-handle" className={labelClass}>Handle <span className="font-normal text-neutral-500">(optional)</span></label>
              <input id="intro-handle" type="text" maxLength={120} value={form.handle ?? ''} placeholder="@yourchannel"
                onChange={(e) => update({ handle: e.target.value })} className={fieldClass} />
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="intro-niche" className={labelClass}>Niche <span className="font-normal text-neutral-500">(optional)</span></label>
              <input id="intro-niche" type="text" list="intro-niches" maxLength={60} value={form.niche ?? ''} placeholder="Gaming, travel, tech…"
                onChange={(e) => update({ niche: e.target.value })} className={fieldClass} />
              <datalist id="intro-niches">
                {NICHES.map((n) => <option key={n} value={n} />)}
              </datalist>
            </div>
            <div>
              <span className={labelClass}>Look</span>
              <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-neutral-950 border border-neutral-800" role="radiogroup" aria-label="Look">
                {THEMES.map((t) => (
                  <button key={t.value} type="button" role="radio" aria-checked={form.theme === t.value} onClick={() => update({ theme: t.value })}
                    className={`h-8 rounded-lg text-xs font-semibold transition-colors ${
                      form.theme === t.value ? 'bg-amber-500/15 text-amber-300' : 'text-neutral-400 hover:text-white'
                    }`}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <span className={labelClass}>Picture</span>
            <div className="flex items-center gap-3">
              <span className="w-14 h-14 rounded-full overflow-hidden bg-neutral-800 border border-neutral-700 shrink-0 flex items-center justify-center text-lg font-bold text-neutral-400">
                {shownAvatar ? <img src={shownAvatar} alt="" className="w-full h-full object-cover" /> : (form.channel_name.trim()[0] || '?').toUpperCase()}
              </span>
              <input ref={fileRef} type="file" accept={INTRO_AVATAR_TYPES.join(',')} className="hidden"
                onChange={(e) => { pickAvatar(e.target.files?.[0]); e.target.value = ''; }} />
              <button type="button" onClick={() => fileRef.current?.click()}
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border border-neutral-700 text-xs font-semibold text-neutral-200 hover:bg-neutral-800">
                <ImagePlus className="w-4 h-4" /> {shownAvatar ? 'Change' : 'Upload'}
              </button>
              {shownAvatar && (
                <button type="button" onClick={() => { setAvatarFile(null); setAvatarPreview(null); setRemoveAvatar(true); }}
                  className="inline-flex items-center gap-1.5 h-9 px-3 rounded-xl text-xs font-semibold text-neutral-400 hover:text-white hover:bg-neutral-800">
                  <Trash2 className="w-4 h-4" /> Remove
                </button>
              )}
              <span className="text-[11px] text-neutral-500">Your profile picture or logo. Without one, your initial is used.</span>
            </div>
          </div>

          <div>
            <label htmlFor="intro-about" className={labelClass}>What’s your channel about?</label>
            <textarea id="intro-about" rows={3} maxLength={2000} value={form.about}
              placeholder="In any language, e.g. Telugu travel vlogs: temples, waterfalls and history across Andhra Pradesh"
              onChange={(e) => update({ about: e.target.value })}
              className={`${fieldClass} h-auto py-2.5 resize-y`} />
          </div>

          <div>
            <label htmlFor="intro-tagline" className={labelClass}>Line shown in the intro</label>
            <input id="intro-tagline" type="text" maxLength={200} value={form.tagline ?? ''}
              placeholder="Leave empty and AI writes it from the description above"
              onChange={(e) => update({ tagline: e.target.value })} className={fieldClass} />
            <p className="text-[11px] text-neutral-500 mt-1">Clear it to have the AI write a new one.</p>
          </div>

          <button type="button" onClick={createIntro} disabled={busy || rendering}
            className="inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
            {busy || rendering ? <Loader2 className="w-4 h-4 animate-spin" /> : intro?.status === 'ready' ? <RefreshCw className="w-4 h-4" /> : <Wand2 className="w-4 h-4" />}
            {rendering ? 'Creating your intro…' : intro?.status === 'ready' ? 'Re-create intro' : 'Create intro'}
            {!allowed && <ProLockBadge feature={FEATURE_LABELS.creator_intro} className="bg-neutral-950/20 text-neutral-950 ring-neutral-950/30" />}
          </button>
        </div>

        <div className="lg:col-span-5 min-w-0 space-y-3">
          <div className="flex items-center justify-between text-xs text-neutral-400">
            <span className="font-semibold">Preview</span>
            <div className="flex gap-1" role="radiogroup" aria-label="Preview size">
              {RENDITIONS.map((r) => (
                <button key={r.value} type="button" role="radio" aria-checked={rendition === r.value} onClick={() => setRendition(r.value)}
                  className={`h-7 px-2.5 rounded-lg text-[11px] font-semibold ${rendition === r.value ? 'bg-neutral-800 text-white' : 'text-neutral-500 hover:text-white'}`}>
                  {r.label}
                </button>
              ))}
            </div>
          </div>
          <div className={`relative mx-auto w-full ${selectedRendition.aspect} rounded-2xl overflow-hidden border border-neutral-800 bg-neutral-950 flex items-center justify-center`}>
            {rendering ? (
              <span className="flex flex-col items-center gap-2 text-xs text-neutral-400 p-4 text-center">
                <Loader2 className="w-5 h-5 animate-spin text-amber-400" /> Writing and rendering your intro…
              </span>
            ) : previewUrl ? (
              <video key={previewUrl} src={previewUrl} controls playsInline className="w-full h-full object-contain" />
            ) : (
              <span className="text-xs text-neutral-500 p-4 text-center">
                {intro?.status === 'failed' ? intro.error || 'The last render failed. Try again.' : 'Your intro shows here once it’s created.'}
              </span>
            )}
          </div>
          {intro?.status === 'ready' && intro.tagline && (
            <p className="text-[11px] text-neutral-500">
              Showing: “{intro.tagline}” · {intro.theme_used === 'dark' ? 'Dark' : 'Light'} look
            </p>
          )}
        </div>
      </div>
    </section>
  );
};
