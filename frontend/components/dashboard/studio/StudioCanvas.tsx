"use client";
import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Eye, ShieldCheck } from 'lucide-react';
import type { AspectRatio, BRollOverlay, CaptionConfig, ViralClip, WordTimestamp } from '@/lib/types';
import { PlatformOverlay } from './PlatformOverlay';
import { captionRowSplit, captionTextStyle } from '@/lib/utils/captionStyles';
import {
  CAPTION_Y_MAX,
  CAPTION_Y_MIN,
  PreviewMode,
  applyEmojiCollection,
  captionEntrance,
  captionWordStyle,
  captionsClear,
  displayWord,
  safeZoneFor,
} from './studioUtils';

/** Caption and title sizes are authored against a 1080px-wide frame, as the burner scales them. */
const CAPTION_REFERENCE_WIDTH = 1080;
/** How long the headline card shows, as TITLE_SECONDS in the burner. */
const TITLE_SECONDS = 5;
const RATIO: Record<AspectRatio, number> = { '9:16': 9 / 16, '4:5': 4 / 5, '1:1': 1, '16:9': 16 / 9 };
/** How close (in % of frame height) a dragged caption must come to a safe-area edge to snap to it. */
const SNAP_DISTANCE = 2.5;

const PREVIEWS: Array<[PreviewMode, string]> = [
  ['none', 'Clean'],
  ['tiktok', 'TikTok'],
  ['reels', 'Reels'],
  ['shorts', 'Shorts'],
];

export const nextPreview = (preview: PreviewMode): PreviewMode =>
  PREVIEWS[(PREVIEWS.findIndex(([id]) => id === preview) + 1) % PREVIEWS.length][0];

export const previewLabel = (preview: PreviewMode): string => PREVIEWS.find(([id]) => id === preview)![1];

interface StudioCanvasProps {
  clip: ViralClip;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  onLoadedMetadata: (duration: number) => void;
  onPlayingChange: (playing: boolean) => void;
  onEnded: () => void;
  aspectRatio: AspectRatio;
  config: CaptionConfig;
  /** Off previews the clip as it exports without captions. */
  showCaptions: boolean;
  showTitle: boolean;
  captionWords: WordTimestamp[];
  hasTranscript: boolean;
  currentTime: number;
  zoomScale: number;
  activeBRoll?: BRollOverlay;
  preview: PreviewMode;
  showSafeZones: boolean;
  onCaptionYChange: (positionY: number) => void;
  /** Phone: a chip on the video cycles the platform preview. */
  onCyclePreview?: () => void;
}

/** The element's rendered width, for scaling text authored against the 1080px frame. */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

export function StudioCanvas(props: StudioCanvasProps) {
  const {
    clip, videoRef, onLoadedMetadata, onPlayingChange, onEnded, aspectRatio, config, showCaptions, showTitle,
    captionWords, hasTranscript, currentTime, zoomScale, activeBRoll, preview, showSafeZones, onCaptionYChange, onCyclePreview,
  } = props;
  const { ref: stageRef, width: stageWidth } = useWidth();
  const [dragging, setDragging] = useState(false);
  const ratio = RATIO[aspectRatio];

  const vertical = aspectRatio === '9:16';
  const zone = safeZoneFor(preview);
  const zonesOn = vertical && showSafeZones;
  const scale = stageWidth > 0 ? stageWidth / CAPTION_REFERENCE_WIDTH : 0.3;
  const captionFontPx = Math.max(9, config.fontSize * scale);
  const titleFontPx = Math.max(9, config.titleFontSize * scale);
  // As burned: each word holds the highlight from its start until the next
  // word starts, and a stacked style splits the line over two rows.
  const activeIndex = captionWords.reduce((found, word, i) => (currentTime >= word.start ? i : found), -1);
  const rowStart = captionRowSplit(captionWords.map((word) => word.text), config.rows);
  const captionRows = [0, 1]
    .map((r) =>
      captionWords
        .map((word, index) => ({ word, index, secondRow: config.rows > 1 && index >= rowStart }))
        .filter(({ secondRow }) => (r === 1) === secondRow),
    )
    .filter((row) => row.length > 0);

  const moveCaption = (clientY: number) => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return;
    let y = ((clientY - rect.top) / rect.height) * 100;
    y = Math.max(CAPTION_Y_MIN, Math.min(CAPTION_Y_MAX, y));
    if (zonesOn) {
      for (const edge of [zone.top, 100 - zone.bottom]) {
        if (Math.abs(y - edge) < SNAP_DISTANCE) y = edge;
      }
    }
    onCaptionYChange(Math.round(y));
  };

  return (
    // A size container, so the stage can be the largest box of its ratio that fits.
    <div className="relative flex-1 min-h-0 min-w-0 flex items-center justify-center [container-type:size]">
      <div
        ref={stageRef}
        className="relative overflow-hidden rounded-xl bg-black shadow-[0_0_0_1px_#2a2a2a,0_30px_60px_-20px_#000] select-none"
        style={{ width: `min(100cqw, calc(100cqh * ${ratio}))`, aspectRatio: String(ratio) }}
      >
        <div
          className="absolute inset-0 transition-transform duration-700 ease-in-out flex items-center justify-center overflow-hidden"
          style={{ transform: `scale(${zoomScale})` }}
        >
          {clip.presignedUrl ? (
            <video
              ref={videoRef}
              src={clip.presignedUrl}
              poster={clip.posterUrl || ''}
              className="w-full h-full object-contain object-center"
              playsInline
              preload="metadata"
              onLoadedMetadata={(e) => {
                const d = e.currentTarget.duration;
                if (d && Number.isFinite(d)) onLoadedMetadata(d);
              }}
              onPlay={() => onPlayingChange(true)}
              onPause={() => onPlayingChange(false)}
              onEnded={onEnded}
            />
          ) : (
            <div className="w-full h-full bg-neutral-800 flex items-center justify-center">
              <p className="text-neutral-400 text-xs">Video not available</p>
            </div>
          )}
        </div>

        {activeBRoll && (
          <div className="absolute inset-0 z-20 animate-in fade-in zoom-in-95 duration-300">
            <img src={activeBRoll.imageUrl} alt={activeBRoll.title} className="w-full h-full object-cover" style={{ opacity: activeBRoll.opacity }} />
            <span className="absolute top-3 left-3 px-2 py-0.5 rounded-full bg-sky-400/20 border border-sky-400/50 text-[10px] font-bold text-sky-100">
              B-roll · {activeBRoll.title}
            </span>
          </div>
        )}

        {zonesOn && (
          <div className="absolute inset-0 z-[25] pointer-events-none" aria-hidden="true">
            {[
              { left: 0, right: 0, top: 0, height: `${zone.top}%` },
              { left: 0, right: 0, bottom: 0, height: `${zone.bottom}%` },
              { right: 0, top: `${zone.top}%`, bottom: `${zone.bottom}%`, width: `${zone.right}%` },
            ].map((style, i) => (
              <div
                key={i}
                className="absolute bg-[repeating-linear-gradient(135deg,rgba(251,113,133,0.16)_0_6px,rgba(251,113,133,0.05)_6px_12px)]"
                style={style}
              />
            ))}
            {dragging && (
              <div className="absolute inset-x-0 border-t border-sky-400/80" style={{ top: `${100 - zone.bottom}%` }}>
                <span className="absolute right-2 top-1 rounded-full bg-sky-950/80 px-2 py-px text-[10px] font-semibold text-sky-200">
                  Safe area edge
                </span>
              </div>
            )}
          </div>
        )}

        {/* The clip's headline card for its opening seconds; mirrors the ASS "Title" and "TitleCard" styles. */}
        {showTitle && clip.title?.trim() && currentTime < TITLE_SECONDS && (
          <div
            className="absolute inset-x-0 z-30 pointer-events-none flex justify-center text-center"
            style={{ top: `${config.titlePositionY}%` }}
          >
            <p
              key={clip.id}
              className="title-card max-w-[80%] bg-white font-bold text-[#141414] [text-wrap:balance] transition-opacity duration-[250ms]"
              style={{
                fontFamily: "'Montserrat', sans-serif",
                fontSize: `${titleFontPx}px`,
                lineHeight: 1.22,
                padding: '0.42em 1.3em',
                borderRadius: '0.22em',
                opacity: currentTime > TITLE_SECONDS - 0.25 ? 0 : 1,
              }}
            >
              {config.emojisEnabled ? applyEmojiCollection(clip.title, config.emojiCollection) : clip.title}
            </p>
          </div>
        )}

        {/* Captions: drag them up or down on the video. */}
        {showCaptions && (
          <div
            className="absolute inset-x-4 z-30 pointer-events-none flex flex-col items-center justify-center text-center"
            style={{ top: `${config.positionY}%`, transform: 'translateY(-50%)' }}
          >
            {captionWords.length > 0 ? (
              <div
                role="slider"
                aria-label="Caption position"
                aria-valuemin={CAPTION_Y_MIN}
                aria-valuemax={CAPTION_Y_MAX}
                aria-valuenow={config.positionY}
                aria-valuetext={`${config.positionY}% from the top`}
                tabIndex={0}
                title="Drag to move the captions"
                onKeyDown={(e) => {
                  if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
                  e.preventDefault();
                  const step = e.key === 'ArrowUp' ? -1 : 1;
                  onCaptionYChange(Math.max(CAPTION_Y_MIN, Math.min(CAPTION_Y_MAX, config.positionY + step)));
                }}
                onPointerDown={(e) => {
                  e.preventDefault();
                  e.currentTarget.setPointerCapture(e.pointerId);
                  setDragging(true);
                }}
                onPointerMove={(e) => dragging && moveCaption(e.clientY)}
                onPointerUp={() => setDragging(false)}
                onPointerCancel={() => setDragging(false)}
                className={`pointer-events-auto touch-none inline-block p-2 rounded-xl outline-offset-4 ${
                  dragging ? 'cursor-grabbing outline-dashed outline-[1.5px] outline-sky-400' : 'cursor-grab hover:outline-dashed hover:outline-[1.5px] hover:outline-sky-400/70'
                } ${config.hasBgBox ? 'shadow-2xl border border-neutral-700/50' : ''}`}
                style={{ backgroundColor: config.hasBgBox ? config.bgBoxColor : 'transparent' }}
              >
                <div
                  key={captionWords[0]?.id}
                  className="leading-[1.1] tracking-tight"
                  style={{
                    ...captionTextStyle(config),
                    animation: captionEntrance(config.animation, config.animationSpeed),
                    fontSize: `${captionFontPx}px`,
                  }}
                >
                  {captionRows.map((row, r) => (
                    <p key={r}>
                      {row.map(({ word, index, secondRow }) => (
                        <span
                          key={word.id}
                          className="caption-motion inline-block mx-[0.12em] px-[0.06em] transition-[color,transform] duration-75"
                          style={captionWordStyle(
                            config,
                            index < activeIndex ? 'spoken' : index === activeIndex ? 'active' : 'upcoming',
                            secondRow ? config.secondLineScale : 1,
                            Boolean(word.highlighted),
                            secondRow,
                          )}
                        >
                          {displayWord(word.text)}
                          {word.emoji && config.emojisEnabled && <span className="ml-1 inline-block animate-pulse">{word.emoji}</span>}
                        </span>
                      ))}
                    </p>
                  ))}
                </div>
              </div>
            ) : !hasTranscript ? (
              <div className="inline-block px-3 py-1.5 rounded-lg bg-black/70 border border-neutral-700/50 text-[10px] text-neutral-400">
                No transcript yet for this clip
              </div>
            ) : null}
          </div>
        )}

        {preview !== 'none' && vertical && (
          <PlatformOverlay platform={preview} title={clip.title} hashtags={clip.socialOptimization.hashtags} />
        )}

        {onCyclePreview && (
          <button
            type="button"
            onClick={onCyclePreview}
            className="absolute top-2 right-2 z-50 h-[26px] px-2.5 inline-flex items-center gap-1 rounded-full bg-black/60 border border-white/20 text-[11px] font-bold text-white"
            aria-label={`Platform preview: ${previewLabel(preview)}. Tap to change.`}
          >
            <Eye className="w-3 h-3" aria-hidden />
            {previewLabel(preview)}
          </button>
        )}
      </div>
    </div>
  );
}

/** Platform preview and safe-zone switch, above the video. */
export function CanvasToolbar({
  preview,
  onPreview,
  showSafeZones,
  onToggleSafeZones,
  aspectRatio,
  compact,
}: {
  preview: PreviewMode;
  onPreview: (preview: PreviewMode) => void;
  showSafeZones: boolean;
  onToggleSafeZones: () => void;
  aspectRatio: AspectRatio;
  compact?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2 px-3.5 py-2.5">
      <div className="flex items-center gap-1.5 min-w-0">
        {!compact && <span className="text-[11.5px] text-neutral-500 whitespace-nowrap">Preview on</span>}
        <div className="inline-flex gap-0.5 p-[3px] rounded-[10px] border border-neutral-800 bg-neutral-900" role="group" aria-label="Preview on platform">
          {PREVIEWS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => onPreview(id)}
              aria-pressed={preview === id}
              className={`h-[26px] px-2.5 rounded-[7px] text-xs font-semibold whitespace-nowrap ${
                preview === id ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onToggleSafeZones}
          aria-pressed={showSafeZones}
          disabled={aspectRatio !== '9:16'}
          title={aspectRatio !== '9:16' ? 'Safe zones apply to 9:16 videos' : undefined}
          className={`h-[30px] px-2.5 inline-flex items-center gap-1.5 rounded-[9px] border text-xs font-semibold whitespace-nowrap disabled:opacity-40 ${
            showSafeZones ? 'border-neutral-700 bg-neutral-900 text-white [&>svg]:text-sky-400' : 'border-neutral-800 bg-neutral-900 text-neutral-400'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" aria-hidden />
          Safe zones
        </button>
        {!compact && (
          <span className="h-[30px] px-2.5 inline-flex items-center rounded-[9px] border border-neutral-800 bg-neutral-900 text-xs font-semibold text-neutral-400">
            {aspectRatio}
          </span>
        )}
      </div>
    </div>
  );
}

/** One line under the video: are the captions clear of the platform's own UI? */
export function CaptionSafetyNote({ positionY, preview, aspectRatio }: { positionY: number; preview: PreviewMode; aspectRatio: AspectRatio }) {
  if (aspectRatio !== '9:16') return null;
  const zone = safeZoneFor(preview);
  const clear = captionsClear(positionY, zone);
  return (
    <p role="status" className={`flex items-center justify-center gap-1.5 pt-2 text-[11.5px] ${clear ? 'text-neutral-400' : 'text-rose-300'}`}>
      {clear ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" aria-hidden /> : <AlertTriangle className="w-3.5 h-3.5 text-rose-400" aria-hidden />}
      {clear
        ? `Captions are clear of ${zone.name} buttons and text`
        : `${zone.name} covers the captions here. Drag them between ${zone.top}% and ${100 - zone.bottom}%.`}
    </p>
  );
}
