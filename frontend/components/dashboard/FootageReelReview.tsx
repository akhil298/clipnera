'use client';

import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowUp, Check, Image as ImageIcon, Loader2, Pause, Play, Sparkles, Type, Undo2, ZoomIn } from 'lucide-react';
import { EDIT_LOOKS, EDIT_MOODS, EditChange, EditResponse, EditSourceResponse, EditTimelineResponse } from '@/lib/api';
import type { CaptionStyle } from '@/lib/utils/captionStyles.generated';
import { CONTENT_TYPE_LABEL, RESOLVED_SCRIPT_LABEL, TARGET_OPTIONS, beatsFrom, formatSeconds, type Beat, type BeatKind } from '@/lib/utils/footageReels';
import { CaptionStylePreview } from './CaptionStylePreview';
import { ReelPreviewPlayer } from './ReelPreviewPlayer';

export interface ChatMessage {
  role: 'user' | 'editor';
  text: string;
  /** What the editor changed, for an editor reply. */
  changed?: string[];
}

const KIND: Record<BeatKind, { label: string; tag: string; segment: string }> = {
  camera: { label: 'On camera', tag: 'bg-neutral-800 text-neutral-200', segment: 'bg-neutral-800 text-neutral-200' },
  broll: { label: 'B-roll', tag: 'bg-sky-500/15 text-sky-200', segment: 'bg-sky-900/70 text-sky-100' },
  photo: { label: 'Photo', tag: 'bg-emerald-500/15 text-emerald-200', segment: 'bg-emerald-900/60 text-emerald-100' },
  card: { label: 'Text card', tag: 'bg-amber-500/15 text-amber-200', segment: 'bg-amber-900/60 text-amber-100' },
};
/** Swatches for the looks in backend/edit_engine/looks.py. */
const LOOK_SWATCH: Record<string, string> = {
  natural: 'bg-[#5E6B62]', clean_bright: 'bg-[#B9C4C9]', warm_film: 'bg-[#A0673A]', teal_orange: 'bg-[linear-gradient(135deg,#2F6F73_50%,#C2783A_50%)]',
  moody: 'bg-[#2C2F3A]', vivid: 'bg-[#C2410C]', bw_punch: 'bg-[linear-gradient(135deg,#E5E5E5_50%,#262626_50%)]',
};
const SUGGESTIONS = ['Make it shorter', 'Punchier hook', 'Calmer music', 'Warmer colours'];
const panel = 'rounded-3xl border border-neutral-800 bg-neutral-900/80';
const chip = (on: boolean) =>
  `h-10 px-3.5 rounded-full border text-[13px] font-semibold transition-colors disabled:opacity-40 ${
    on ? 'border-amber-500 bg-amber-500/15 text-amber-200' : 'border-neutral-800 text-neutral-300 hover:text-white hover:border-neutral-700'
  }`;
const capitalise = (word: string) => word[0].toUpperCase() + word.slice(1);

function BeatThumb({ beat }: { beat: Beat }) {
  const url = beat.source?.url;
  if (beat.kind === 'card') return <Type className="w-4 h-4 text-amber-300" />;
  if (!url) return <ImageIcon className="w-4 h-4 text-neutral-600" />;
  return beat.kind === 'photo'
    ? <img src={url} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover" />
    : <video src={`${url}#t=${beat.sourceStart.toFixed(2)}`} muted playsInline preload="metadata" aria-hidden="true" className="absolute inset-0 w-full h-full object-cover" />;
}

/** The reel shot by shot; memoised so the playing preview only re-renders it when the shot changes. */
const Story = memo(function Story({ beats, active, hook, onPick }: {
  beats: Beat[]; active: number; hook: string; onPick: (beat: Beat) => void;
}) {
  return (
    <ol className="space-y-2 overflow-y-auto max-h-[560px] pr-1 -mr-1 [scrollbar-width:thin]">
      {beats.map((beat) => (
        <li key={beat.index}>
          <button type="button" onClick={() => onPick(beat)} aria-current={beat.index === active ? 'step' : undefined}
            className={`w-full flex gap-3 p-2.5 rounded-2xl border-[1.5px] text-left transition-colors ${
              beat.index === active ? 'border-amber-500/60 bg-amber-500/[0.07]' : 'border-neutral-800 bg-neutral-950 hover:border-neutral-700'
            }`}>
            <span className="relative w-[52px] aspect-[9/16] rounded-[10px] overflow-hidden bg-neutral-900 shrink-0 flex items-center justify-center">
              <BeatThumb beat={beat} />
              <span className="absolute top-1 left-1.5 font-mono text-[11px] font-semibold text-white [text-shadow:0_1px_2px_rgba(0,0,0,.9)]">{beat.index + 1}</span>
            </span>
            <span className="min-w-0 flex-1 space-y-1">
              <span className="flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-xs text-neutral-400">{formatSeconds(beat.at)}–{formatSeconds(beat.at + beat.dur)}</span>
                {beat.index === 0 && hook && <span className="px-2 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-200">Hook</span>}
                <span className={`px-2 rounded-full text-[11px] font-bold ${KIND[beat.kind].tag}`}>{KIND[beat.kind].label}</span>
              </span>
              <span className="block text-sm text-neutral-200 leading-snug line-clamp-3">{beat.line ? `“${beat.line}”` : beat.source?.name ?? 'No words'}</span>
              {(beat.zoomed || beat.pops.length > 0) && (
                <span className="flex flex-wrap gap-x-3 text-xs text-neutral-500">
                  {beat.zoomed && <span className="inline-flex items-center gap-1"><ZoomIn className="w-3 h-3" /> Punch-in</span>}
                  {beat.pops.map((pop) => <span key={pop}>Pop-up “{pop}”</span>)}
                </span>
              )}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
});

function Timeline({ beats, duration, t, active, onPick, captionName, musicName }: {
  beats: Beat[]; duration: number; t: number; active: number; onPick: (beat: Beat) => void; captionName: string; musicName: string;
}) {
  const ticks = Array.from({ length: 6 }, (_, i) => (duration * i) / 5);
  return (
    <section aria-label="Timeline" className={`${panel} p-4 sm:px-5 space-y-2.5`}>
      <div className="flex justify-between font-mono text-xs text-neutral-500" aria-hidden="true">
        {ticks.map((tick) => <span key={tick}>{formatSeconds(tick)}</span>)}
      </div>
      <div className="relative space-y-1.5">
        <div className="flex gap-[3px] h-16">
          {beats.map((beat) => (
            <button key={beat.index} type="button" onClick={() => onPick(beat)} aria-label={`Shot ${beat.index + 1}, ${KIND[beat.kind].label}, at ${formatSeconds(beat.at)}`}
              style={{ flex: `${Math.max(0.3, beat.dur)} 1 0` }}
              className={`min-w-0 rounded-[10px] px-2 pb-2 flex items-end text-xs font-semibold border-2 ${KIND[beat.kind].segment} ${beat.index === active ? 'border-amber-400' : 'border-transparent hover:border-neutral-600'}`}>
              <span className="truncate">{beat.index + 1}</span>
            </button>
          ))}
        </div>
        <div className="h-7 rounded-lg bg-amber-500/10 px-2.5 flex items-center text-xs font-semibold text-amber-200 truncate">Captions · {captionName}</div>
        <div className="h-7 rounded-lg bg-sky-500/10 px-2.5 flex items-center text-xs font-semibold text-sky-200 truncate">Music · {musicName}</div>
        <span className="pointer-events-none absolute -top-1.5 -bottom-1.5 w-0.5 rounded bg-white" style={{ left: `${(t / Math.max(duration, 0.01)) * 100}%` }} aria-hidden="true" />
      </div>
    </section>
  );
}

function Chat({ edit, messages, onSend, busy, canEdit }: {
  edit: EditResponse; messages: ChatMessage[]; onSend: (message: string) => Promise<boolean>; busy: boolean; canEdit: boolean;
}) {
  const [draft, setDraft] = useState('');
  const plan = edit.plan!;
  const usable = canEdit && edit.chat_edits_left > 0;
  const send = async (text: string) => {
    if (!text.trim() || !usable) return;
    if (await onSend(text.trim())) setDraft('');
  };
  const summary = [
    `Opens on “${plan.hook || plan.title}”.`,
    `${CONTENT_TYPE_LABEL[plan.content_type] ?? plan.content_type}, ${formatSeconds(edit.duration_s)} from ${formatSeconds(edit.raw_seconds)} of footage.`,
    `${plan.broll_count} B-roll shot${plan.broll_count === 1 ? '' : 's'}, ${plan.pop_count} pop-up${plan.pop_count === 1 ? '' : 's'}, ${plan.music ? `${plan.music_mood} music` : 'no music'}, ${EDIT_LOOKS[plan.look] ?? plan.look} look.`,
    RESOLVED_SCRIPT_LABEL[plan.script_mode] + '.',
  ].join(' ');

  return (
    <section aria-labelledby="reel-chat" className={`${panel} flex flex-col overflow-hidden`}>
      <div className="px-5 py-4 border-b border-neutral-800 flex items-center gap-2.5">
        <span className="w-8 h-8 rounded-[10px] bg-amber-500/15 text-amber-300 flex items-center justify-center"><Sparkles className="w-4 h-4" /></span>
        <h2 id="reel-chat" className="font-syne text-lg font-bold text-white">Ask the editor</h2>
        <span className="ml-auto text-[13px] text-neutral-400">{edit.chat_edits_left} change{edit.chat_edits_left === 1 ? '' : 's'} left</span>
      </div>
      <div className="flex-1 min-h-[220px] max-h-[460px] overflow-y-auto p-5 space-y-3" aria-live="polite">
        <div className="rounded-2xl bg-neutral-800/60 px-4 py-3.5 space-y-1.5">
          <p className="text-xs font-bold text-amber-300">The plan{plan.director_model ? ` · ${plan.director_model}` : ''}</p>
          <p className="text-[15px] text-neutral-100">{summary}</p>
        </div>
        {messages.map((m, i) => m.role === 'user' ? (
          <p key={i} className="ml-auto max-w-[85%] w-fit rounded-[18px] rounded-br-md bg-amber-500/15 px-4 py-3 text-[15px] text-amber-50">{m.text}</p>
        ) : (
          <div key={i} className="rounded-2xl bg-neutral-800/60 px-4 py-3.5 space-y-2">
            <p className="text-[15px] text-neutral-100">{m.text}</p>
            {m.changed && m.changed.length > 0 && (
              <span className="flex flex-wrap gap-1.5">
                {m.changed.map((name) => (
                  <span key={name} className="h-7 inline-flex items-center gap-1 px-2.5 rounded-full bg-emerald-500/15 text-xs font-semibold text-emerald-200">
                    <Check className="w-3 h-3" /> {capitalise(name)}
                  </span>
                ))}
              </span>
            )}
          </div>
        ))}
        {busy && <p className="flex items-center gap-2 text-sm text-neutral-400"><Loader2 className="w-4 h-4 animate-spin" /> Working on it…</p>}
      </div>
      <div className="px-4 pb-2.5 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button key={s} type="button" disabled={!usable || busy} onClick={() => send(s)}
            className="h-9 px-3 rounded-full border border-neutral-800 text-[13px] text-neutral-300 hover:text-white hover:border-neutral-700 disabled:opacity-40">{s}</button>
        ))}
      </div>
      <form className="mx-3 mb-3 rounded-[18px] border border-neutral-700 bg-neutral-950 px-3.5 py-3 space-y-2.5 focus-within:border-amber-400/70"
        onSubmit={(e) => { e.preventDefault(); send(draft); }}>
        <label htmlFor="reel-chat-input" className="sr-only">Tell the editor what to change</label>
        <textarea id="reel-chat-input" rows={2} value={draft} maxLength={300} disabled={!usable}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
          placeholder={edit.chat_edits_left === 0 ? "You've used this reel's chat changes. Change the plan directly." : 'Tell the editor what to change…'}
          className="w-full resize-none bg-transparent border-0 p-0 text-[15px] text-white placeholder:text-neutral-600 focus:outline-none disabled:opacity-60" />
        <div className="flex flex-wrap items-center gap-1.5">
          <button type="submit" disabled={!usable || busy || !draft.trim()} aria-label="Send"
            className="ml-auto w-11 h-11 rounded-[14px] bg-amber-500 hover:bg-amber-400 text-neutral-950 flex items-center justify-center disabled:opacity-40">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUp className="w-5 h-5" />}
          </button>
        </div>
      </form>
    </section>
  );
}

function MusicCard({ edit, canEdit, change }: { edit: EditResponse; canEdit: boolean; change: (...c: EditChange[]) => void }) {
  const plan = edit.plan!;
  const [audio] = useState(() => (typeof Audio === 'undefined' ? null : new Audio()));
  const [playing, setPlaying] = useState(false);
  useEffect(() => () => audio?.pause(), [audio]);
  const toggle = () => {
    if (!audio || !plan.music?.url) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
      return;
    }
    if (audio.src !== plan.music.url) audio.src = plan.music.url;
    audio.onended = () => setPlaying(false);
    audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  };
  return (
    <div className={`${panel} p-5 space-y-3`}>
      <p className="text-[13px] font-semibold text-neutral-400">Music</p>
      <div className="flex items-center gap-3">
        <button type="button" onClick={toggle} disabled={!plan.music?.url} aria-label={playing ? 'Pause the track' : 'Play the track'}
          className="w-11 h-11 shrink-0 rounded-xl bg-sky-500/15 text-sky-200 flex items-center justify-center disabled:opacity-40">
          {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>
        <div className="min-w-0">
          <p className="text-[15px] font-semibold text-white truncate">{plan.music ? plan.music.title : 'No music'}</p>
          {plan.music && <p className="text-[13px] text-neutral-400 truncate">{plan.music.artist} · {plan.music.licence}</p>}
        </div>
      </div>
      <div role="group" aria-label="Music mood" className="flex flex-wrap gap-1.5">
        {[...EDIT_MOODS, 'none' as const].map((mood) => {
          const on = mood === 'none' ? !plan.music : Boolean(plan.music) && plan.music_mood === mood;
          return (
            <button key={mood} type="button" disabled={!canEdit} aria-pressed={on} onClick={() => !on && change({ op: 'set_music', value: mood })} className={chip(on)}>
              {mood === 'none' ? 'No music' : capitalise(mood)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** The plan to look at and change: the story, a big preview, the chat, a timeline and the style. */
export function FootageReelReview({ edit, preview, canEdit, busy, maxOutput, captionOptions, change, messages, onSend }: {
  edit: EditResponse;
  preview: { timeline: EditTimelineResponse; sources: EditSourceResponse[]; music: string | null };
  canEdit: boolean;
  busy: boolean;
  maxOutput: number;
  captionOptions: CaptionStyle[];
  change: (...changes: EditChange[]) => void;
  messages: ChatMessage[];
  onSend: (message: string) => Promise<boolean>;
}) {
  const plan = edit.plan!;
  const [t, setT] = useState(0);
  const [seek, setSeek] = useState<{ to: number; n: number }>();
  const [hook, setHook] = useState(plan.hook);
  const [hookFor, setHookFor] = useState(plan.hook);
  if (hookFor !== plan.hook) {
    // A new plan or a chat change brings its own hook into the box.
    setHookFor(plan.hook);
    setHook(plan.hook);
  }
  const beats = useMemo(() => beatsFrom(preview.timeline, preview.sources), [preview]);
  const active = beats.findIndex((b) => b.at <= t && t < b.at + b.dur);
  const pick = useCallback((beat: Beat) => setSeek((prev) => ({ to: beat.at + 0.01, n: (prev?.n ?? 0) + 1 })), []);
  // Eighth-second steps: the playhead still moves smoothly, and this page re-renders 8 times a second, not 60.
  const onTime = useCallback((time: number) => setT(Math.floor(time * 8) / 8), []);
  const captionName = captionOptions.find((s) => s.id === plan.caption_style)?.name ?? plan.caption_style;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-5 items-stretch">
        <section aria-labelledby="reel-story" className={`${panel} flex-[1_1_300px] min-w-0 p-4 sm:p-5 space-y-3`}>
          <div className="flex flex-wrap items-baseline gap-x-2">
            <h2 id="reel-story" className="font-syne text-xl font-bold text-white">The story</h2>
            <span className="text-[13px] text-neutral-400">{beats.length} shots · tap one to jump there</span>
          </div>
          {edit.reference && (
            <p className="rounded-2xl border border-amber-500/30 bg-amber-500/[0.07] px-3.5 py-2.5 text-[13px] text-amber-100">
              <span className="font-semibold">From your reference:</span> a cut every {edit.reference.seconds_per_shot.toFixed(1)} s, {edit.reference.energy} energy.
              {edit.reference.style ? ` ${edit.reference.style}` : ''}
            </p>
          )}
          {edit.reference_error && <p className="rounded-2xl border border-neutral-700 px-3.5 py-2.5 text-[13px] text-neutral-300">{edit.reference_error}</p>}
          {plan.missing_lines.length > 0 && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-[13px] text-amber-100 space-y-1.5">
              <p>{plan.missing_lines.length} script line{plan.missing_lines.length > 1 ? 's weren’t' : ' wasn’t'} said on camera
                {plan.skip_missing ? ' and will be left out.' : ' and will show as a text card.'}</p>
              <ul className="list-disc pl-4 text-amber-200/80">{plan.missing_lines.map((l) => <li key={l}>{l}</li>)}</ul>
              <button type="button" disabled={!canEdit} onClick={() => change({ op: 'skip_missing_lines', value: plan.skip_missing ? 'false' : 'true' })}
                className="min-h-9 font-semibold text-amber-300 hover:text-amber-200">
                {plan.skip_missing ? 'Show them as text cards' : 'Leave them out'}
              </button>
            </div>
          )}
          <Story beats={beats} active={active} hook={plan.hook} onPick={pick} />
          {plan.removed_lines.length > 0 && (
            <details className="border-t border-neutral-800 pt-3">
              <summary className="cursor-pointer min-h-9 text-sm font-semibold text-neutral-200">
                Left out · {plan.removed_lines.length} line{plan.removed_lines.length === 1 ? '' : 's'} (retakes, off-script or trimmed)
              </summary>
              <ul className="mt-2 space-y-1">
                {plan.removed_lines.map((line) => (
                  <li key={line.id} className="flex items-center gap-2 text-[13px] text-neutral-400">
                    <span className="flex-1 line-clamp-2">“{line.text}”</span>
                    <button type="button" disabled={!canEdit} onClick={() => change({ op: 'restore_line', value: line.id })}
                      className="shrink-0 inline-flex items-center gap-1 h-9 px-2.5 rounded-lg font-semibold text-amber-300 hover:bg-amber-500/10 disabled:opacity-40">
                      <Undo2 className="w-3.5 h-3.5" /> Restore
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>

        <section aria-label="Preview" className="flex-[0_1_400px] min-w-[280px] flex justify-center">
          <ReelPreviewPlayer timeline={preview.timeline} sources={preview.sources} musicUrl={preview.music} seek={seek} onTime={onTime} />
        </section>

        <div className="flex-[1_1_320px] min-w-0">
          <Chat edit={edit} messages={messages} onSend={onSend} busy={busy} canEdit={canEdit} />
        </div>
      </div>

      <Timeline beats={beats} duration={preview.timeline.duration} t={t} active={active} onPick={pick}
        captionName={captionName} musicName={plan.music ? `${plan.music_mood} · ${plan.music.title}` : 'none'} />

      <section aria-label="Style" className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(260px,1fr))]">
        <MusicCard edit={edit} canEdit={canEdit} change={change} />

        <div className={`${panel} p-5 space-y-3`}>
          <p className="text-[13px] font-semibold text-neutral-400">Colour look</p>
          <div role="group" aria-label="Colour look" className="grid grid-cols-4 gap-2">
            {Object.entries(EDIT_LOOKS).map(([id, name]) => (
              <button key={id} type="button" disabled={!canEdit} aria-pressed={plan.look === id} onClick={() => plan.look !== id && change({ op: 'set_look', value: id })}
                className={`min-w-0 p-1.5 rounded-xl border-[1.5px] bg-neutral-950 space-y-1.5 disabled:opacity-40 ${plan.look === id ? 'border-amber-500' : 'border-neutral-800 hover:border-neutral-700'}`}>
                <span className={`block h-10 rounded-lg ${LOOK_SWATCH[id] ?? 'bg-neutral-700'}`} />
                <span className="block text-[11.5px] font-semibold text-neutral-300 truncate">{name}</span>
              </button>
            ))}
          </div>
        </div>

        <div className={`${panel} p-5 space-y-3`}>
          <p className="text-[13px] font-semibold text-neutral-400">Captions · {captionName}</p>
          <div role="group" aria-label="Caption style" className="grid grid-cols-2 gap-2 max-h-[236px] overflow-y-auto pr-1 [scrollbar-width:thin]">
            {captionOptions.map((style) => (
              <button key={style.id} type="button" disabled={!canEdit} aria-pressed={plan.caption_style === style.id}
                onClick={() => plan.caption_style !== style.id && change({ op: 'set_caption_style', value: style.id })}
                className={`h-[72px] rounded-xl border-[1.5px] bg-neutral-950 overflow-hidden flex flex-col items-center justify-center gap-1 disabled:opacity-40 ${plan.caption_style === style.id ? 'border-amber-500' : 'border-neutral-800 hover:border-neutral-700'}`}>
                <CaptionStylePreview config={style.config} words={['MADE', 'IT']} fontSize={15} overlay />
                <span className="text-[11.5px] font-semibold text-neutral-400">{style.name}</span>
              </button>
            ))}
          </div>
        </div>

        <div className={`${panel} p-5 space-y-3`}>
          <p className="text-[13px] font-semibold text-neutral-400">Length · {formatSeconds(edit.duration_s)}</p>
          <div role="group" aria-label="Target length" className="flex flex-wrap gap-1.5">
            {TARGET_OPTIONS.filter((s) => s <= maxOutput).map((s) => (
              <button key={s} type="button" disabled={!canEdit} aria-pressed={edit.target_seconds === s}
                onClick={() => edit.target_seconds !== s && change({ op: 'set_length', value: String(s) })} className={chip(edit.target_seconds === s)}>
                {s === 0 ? 'Auto' : `${s} s`}
              </button>
            ))}
          </div>
          <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); change({ op: 'set_hook', value: hook }); }}>
            <label htmlFor="plan-hook" className="block text-[13px] text-neutral-400">Hook headline</label>
            <div className="flex gap-2">
              <input id="plan-hook" value={hook} onChange={(e) => setHook(e.target.value)} maxLength={60} disabled={!canEdit}
                className="flex-1 min-w-0 h-11 px-3.5 rounded-xl bg-neutral-950 border border-neutral-800 text-[15px] text-white focus:outline-none focus:border-amber-400" />
              {hook !== plan.hook && (
                <button type="submit" disabled={!canEdit} className="h-11 px-4 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-sm font-semibold text-white">Save</button>
              )}
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
