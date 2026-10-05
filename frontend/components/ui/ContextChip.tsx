import { Captions, Clock, Film, Image as ImageIcon, MoveHorizontal, X } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

export type ContextKind = 'clip' | 'range' | 'caption' | 'asset' | 'moment';

export interface PromptContext {
  id: string;
  kind: ContextKind;
  /** Clip title, `0:12 – 0:31`, first words of a caption line, asset name, or timecode. */
  label: string;
  /** Secondary detail, e.g. a clip's duration. */
  meta?: string;
  /** Asset thumbnail. Decorative; the label names the asset. */
  thumbnailUrl?: string;
}

const KIND: Record<ContextKind, { icon: ReactNode; noun: string }> = {
  clip: { icon: <Film />, noun: 'Clip' },
  range: { icon: <MoveHorizontal />, noun: 'Range' },
  caption: { icon: <Captions />, noun: 'Caption line' },
  asset: { icon: <ImageIcon />, noun: 'Asset' },
  moment: { icon: <Clock />, noun: 'Moment' },
};

export interface ContextChipProps {
  context: PromptContext;
  /** Removes the chip from the prompt. Omit for a read-only chip (in a sent message). */
  onRemove?: (id: string) => void;
  className?: string;
}

/**
 * What the next prompt applies to: whatever is selected attaches here
 * ("Point, then prompt", 01 §3.8). Read as "Clip: Opening hook, 0:42".
 */
export function ContextChip({ context, onRemove, className }: ContextChipProps) {
  const { kind, label, meta, thumbnailUrl } = context;
  const { icon, noun } = KIND[kind];
  return (
    <span
      className={cx(
        'inline-flex h-7 max-w-[16rem] items-center gap-1.5 rounded-cn-sm border border-cn-border-strong bg-cn-surface pl-1.5 text-cn-label text-cn-fg',
        onRemove ? 'pr-0.5' : 'pr-2',
        className,
      )}
    >
      {thumbnailUrl ? (
        <img src={thumbnailUrl} alt="" className="size-5 shrink-0 rounded-cn-xs object-cover" />
      ) : (
        <span aria-hidden className="inline-flex shrink-0 text-cn-accent-text [&_svg]:size-3.5">
          {icon}
        </span>
      )}
      <span className="sr-only">{noun}: </span>
      <span className={cx('truncate', kind === 'range' || kind === 'moment' ? 'font-cn-mono text-cn-caption tabular-nums' : '')}>
        {label}
      </span>
      {meta && <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{meta}</span>}
      {onRemove && (
        <button
          type="button"
          onClick={() => onRemove(context.id)}
          aria-label={`Remove ${noun.toLowerCase()} ${label} from the prompt`}
          className={cx(
            'inline-flex size-6 shrink-0 items-center justify-center rounded-cn-xs text-cn-fg-muted hover:bg-cn-surface-hover hover:text-cn-fg [&_svg]:size-3.5',
            focusRing,
          )}
        >
          <X aria-hidden />
        </button>
      )}
    </span>
  );
}
