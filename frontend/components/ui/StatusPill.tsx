import React from 'react';
import type { VideoProject } from '@/lib/types';

/**
 * One status language for the whole app: a dot plus a word, with the same
 * colour meaning everywhere (processing amber, ready green, failed rose,
 * scheduled sky, AI violet).
 */
export type StatusTone = 'processing' | 'ready' | 'failed' | 'scheduled' | 'neutral' | 'ai';

const TONE_CLASSES: Record<StatusTone, { pill: string; dot: string }> = {
  processing: { pill: 'bg-amber-500/10 text-amber-300 border-amber-500/20', dot: 'bg-amber-400' },
  ready: { pill: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20', dot: 'bg-emerald-400' },
  failed: { pill: 'bg-rose-500/10 text-rose-300 border-rose-500/20', dot: 'bg-rose-400' },
  scheduled: { pill: 'bg-sky-500/10 text-sky-300 border-sky-500/20', dot: 'bg-sky-400' },
  neutral: { pill: 'bg-neutral-800/80 text-neutral-300 border-neutral-700/60', dot: 'bg-neutral-500' },
  ai: { pill: 'bg-violet-500/10 text-violet-300 border-violet-500/20', dot: 'bg-violet-400' },
};

export const statusDotClass = (tone: StatusTone): string => TONE_CLASSES[tone].dot;

interface StatusPillProps {
  tone: StatusTone;
  children: React.ReactNode;
  /** Hide the leading dot, e.g. when an icon is passed as a child. */
  dot?: boolean;
  className?: string;
  title?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({ tone, children, dot = true, className = '', title }) => (
  <span
    title={title}
    className={`inline-flex items-center gap-1.5 h-6 px-2 rounded-full border text-[11px] font-bold whitespace-nowrap ${TONE_CLASSES[tone].pill} ${className}`}
  >
    {dot && (
      <span
        className={`w-1.5 h-1.5 rounded-full shrink-0 ${TONE_CLASSES[tone].dot} ${tone === 'processing' ? 'animate-pulse' : ''}`}
      />
    )}
    {children}
  </span>
);

/** The status a project shows in lists, pills and the sidebar. */
export const projectStatus = (project: VideoProject): { tone: StatusTone; label: string } => {
  switch (project.processingStatus) {
    case 'processing':
      return { tone: 'processing', label: 'Processing' };
    case 'failed':
      return { tone: 'failed', label: 'Failed' };
    default:
      return project.clips.length > 0
        ? { tone: 'ready', label: 'Ready' }
        : { tone: 'neutral', label: 'No clips yet' };
  }
};
