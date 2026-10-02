"use client";
import React from 'react';
import type { CaptionConfig, FormatItem } from '@/lib/types';
import type { FormatOverlay } from '@/lib/formats';

// Mirrors backend/subtitle_styling/format_overlay.py; sizes are px on a 1080px short side.
const COUNTER_EM = 60;
const LABEL_EM = 44;
const BOARD_ROW_PX = 64;
const BOARD_WIDTH = 0.46;
const CLEARANCE = 24;
const SAFE_TOP = 0.04;
const SAFE_BOTTOM = 0.94;

interface FormatOverlayPreviewProps {
  overlay: FormatOverlay;
  items: FormatItem[];
  currentTime: number;
  config: CaptionConfig;
  /** Whether the headline card is on, whose space the overlay keeps clear of. */
  titleOn: boolean;
  titleFontPx: number;
  captionFontPx: number;
  stageWidth: number;
  stageHeight: number;
}

/** Black or white, whichever reads on a '#RRGGBB' colour, as the burner picks. */
function contrastOn(hex: string): string {
  const clean = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(clean.slice(i, i + 2), 16) || 0);
  return 0.299 * r + 0.587 * g + 0.114 * b > 150 ? '#000000' : '#FFFFFF';
}

/** The topmost free stretch of the frame `needed` px tall, else the tallest one. */
function freeBand(occupied: Array<[number, number]>, height: number, clearance: number, needed: number): [number, number] {
  const blocked = occupied.map(([low, high]) => [low - clearance, high + clearance]).sort((a, b) => a[0] - b[0]);
  const free: Array<[number, number]> = [];
  let cursor = SAFE_TOP * height;
  for (const [low, high] of blocked) {
    if (low > cursor) free.push([cursor, Math.min(low, SAFE_BOTTOM * height)]);
    cursor = Math.max(cursor, high);
  }
  if (cursor < SAFE_BOTTOM * height) free.push([cursor, SAFE_BOTTOM * height]);
  const usable = free.filter(([low, high]) => high > low);
  if (usable.length === 0) return [SAFE_TOP * height, SAFE_BOTTOM * height];
  return (
    usable.find(([low, high]) => high - low >= needed) ??
    usable.reduce((best, band) => (band[1] - band[0] > best[1] - best[0] ? band : best))
  );
}

/**
 * The list overlay the export burns over a listicle or ranking: a counter with
 * the item's label, or a board of ranks down the right side. Placed by the
 * same rule as the burner, from what the preview knows of the title and captions.
 */
export function FormatOverlayPreview(props: FormatOverlayPreviewProps) {
  const { overlay, items, currentTime, config, titleOn, titleFontPx, captionFontPx, stageWidth, stageHeight } = props;
  if (overlay === 'none' || items.length < 2 || stageWidth <= 0 || stageHeight <= 0) return null;

  const s = Math.min(stageWidth, stageHeight) / 1080;
  const captionY = (config.positionY / 100) * stageHeight;
  const captionReach = 1.2 * captionFontPx * Math.max(1, config.rows);
  const occupied: Array<[number, number]> = [[captionY - captionReach, captionY + captionReach]];
  if (titleOn) {
    const titleTop = (config.titlePositionY / 100) * stageHeight;
    // Two lines of headline on its card.
    occupied.push([titleTop, titleTop + titleFontPx * 3]);
  }
  const accent = config.highlightColor;
  const ink = contrastOn(accent);
  const outline = `0 0 ${3 * s}px #000, 0 0 ${3 * s}px #000`;

  if (overlay === 'list_counter') {
    const [top] = freeBand(occupied, stageHeight, CLEARANCE * s, (COUNTER_EM * 1.56 + LABEL_EM * 2.8) * s);
    const item = items.find((i) => currentTime >= i.start && currentTime < i.end);
    if (!item) return null;
    return (
      <div className="absolute inset-x-0 z-20 pointer-events-none flex flex-col items-center text-center" style={{ top }}>
        <span
          className="rounded-full font-bold"
          style={{
            background: accent, color: ink, fontFamily: "'Montserrat', sans-serif",
            fontSize: COUNTER_EM * s, lineHeight: 1, padding: `${0.28 * COUNTER_EM * s}px ${0.55 * COUNTER_EM * s}px`,
          }}
        >
          {item.number}/{items.length}
        </span>
        <span
          className="max-w-[82%] font-bold text-white [text-wrap:balance]"
          style={{ fontFamily: "'Montserrat', sans-serif", fontSize: LABEL_EM * s, lineHeight: 1.15, marginTop: 0.3 * LABEL_EM * s, textShadow: outline }}
        >
          {item.label}
        </span>
      </div>
    );
  }

  const slots = Math.max(...items.map((i) => i.rank ?? 0));
  if (slots < 1 || currentTime < items[0].start) return null;
  const [top, bottom] = freeBand(occupied, stageHeight, CLEARANCE * s, Math.min(slots, 5) * BOARD_ROW_PX * s);
  const rowHeight = Math.min(BOARD_ROW_PX * s, (bottom - top) / slots);
  const fontSize = 0.52 * rowHeight;
  return (
    <div
      className="absolute z-20 pointer-events-none overflow-hidden"
      style={{
        top, right: CLEARANCE * s, width: stageWidth * BOARD_WIDTH, height: rowHeight * slots,
        borderRadius: 0.3 * rowHeight, background: 'rgba(0,0,0,0.62)', fontFamily: "'Montserrat', sans-serif",
      }}
    >
      {Array.from({ length: slots }, (_, index) => {
        const rank = index + 1;
        const item = items.find((i) => i.rank === rank && currentTime >= i.start);
        const active = item != null && currentTime < item.end;
        return (
          <div
            key={rank}
            className="flex items-center font-bold"
            style={{ height: rowHeight, fontSize, gap: 0.25 * fontSize, padding: `0 ${0.35 * fontSize}px` }}
          >
            <span style={{ color: accent }}>{rank}.</span>
            {item && (
              <span
                className="truncate"
                style={{
                  color: active ? ink : '#FFFFFF', background: active ? accent : 'transparent',
                  borderRadius: 0.3 * rowHeight, padding: `${0.2 * fontSize}px ${0.25 * fontSize}px`,
                }}
              >
                {item.label}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
