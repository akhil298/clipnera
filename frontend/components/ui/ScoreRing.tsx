import React from 'react';

const RADIUS = 15;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Amber above 85, green above 70, neutral below, so the eye finds the strong clips first. */
export function scoreTone(score: number): { ring: string; text: string; chip: string } {
  if (score >= 85) {
    return { ring: 'stroke-amber-400', text: 'text-amber-300', chip: 'bg-amber-500/15 text-amber-300 border-amber-500/30' };
  }
  if (score >= 70) {
    return { ring: 'stroke-emerald-400', text: 'text-emerald-300', chip: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25' };
  }
  return { ring: 'stroke-neutral-500', text: 'text-neutral-300', chip: 'bg-neutral-800 text-neutral-300 border-neutral-700' };
}

interface ScoreRingProps {
  score: number;
  className?: string;
}

/** A clip's virality score as a dial, readable on top of any poster. */
/** Pass positioning in className (e.g. "absolute top-2 right-2 h-9 w-9"); it defaults to relative. */
export const ScoreRing: React.FC<ScoreRingProps> = ({ score, className = 'relative h-9 w-9' }) => {
  const tone = scoreTone(score);
  const clamped = Math.min(100, Math.max(0, score));
  return (
    <div className={className} role="img" aria-label={`Virality score ${score} out of 100`}>
      <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
        <circle cx="18" cy="18" r={RADIUS} fill="rgba(0,0,0,0.65)" stroke="rgba(255,255,255,0.12)" strokeWidth="3" />
        <circle
          cx="18"
          cy="18"
          r={RADIUS}
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          className={tone.ring}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - clamped / 100)}
        />
      </svg>
      <span className={`absolute inset-0 flex items-center justify-center text-[11px] font-extrabold tabular-nums ${tone.text}`}>
        {score}
      </span>
    </div>
  );
};
