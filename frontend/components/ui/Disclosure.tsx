'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { type ReactNode, useId } from 'react';

import { collapseTransition } from '@/lib/design/motion';
import { cx, focusRing } from '@/lib/design/styles';
import { useControllableState } from '@/lib/design/useControllableState';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

export interface DisclosureProps {
  title: ReactNode;
  /** One line shown beside the title while closed: "Auto · 9:16 · English". */
  summary?: ReactNode;
  children: ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** The trigger sits in a heading of this level, so the section shows in the outline. Default 3. */
  level?: 2 | 3 | 4;
  /** `card` draws a bordered surface; `plain` is a bare row (inside a panel). */
  variant?: 'plain' | 'card';
  disabled?: boolean;
  className?: string;
}

/**
 * Show-more for optional detail: upload Options, run Details, an FAQ answer.
 * A button inside a heading with `aria-expanded`; height collapses in 200 ms,
 * instantly under reduced motion.
 */
export function Disclosure({
  title,
  summary,
  children,
  open,
  defaultOpen = false,
  onOpenChange,
  level = 3,
  variant = 'plain',
  disabled = false,
  className,
}: DisclosureProps) {
  const id = useId();
  const reduced = useReducedMotion();
  const [isOpen, setOpen] = useControllableState(open, defaultOpen, onOpenChange);
  const Heading = `h${level}` as const;
  const card = variant === 'card';

  return (
    <div className={cx(card && 'rounded-cn-lg border border-cn-border bg-cn-surface', className)}>
      <Heading className="text-cn-body">
        <button
          type="button"
          aria-expanded={isOpen}
          aria-controls={`${id}-panel`}
          disabled={disabled}
          onClick={() => setOpen(!isOpen)}
          className={cx(
            'flex min-h-10 w-full items-center gap-3 text-left font-semibold text-cn-fg transition-colors duration-cn-fast',
            'hover:text-cn-fg disabled:cursor-not-allowed disabled:opacity-50',
            card ? 'rounded-cn-lg px-4 hover:bg-cn-surface-hover' : 'rounded-cn-sm',
            focusRing,
          )}
        >
          <span className="min-w-0 flex-1 truncate">{title}</span>
          {summary && !isOpen && <span className="hidden min-w-0 truncate text-cn-label font-normal text-cn-fg-muted sm:block">{summary}</span>}
          <ChevronDown
            aria-hidden
            className={cx('size-4 shrink-0 text-cn-fg-muted motion-safe:transition-transform motion-safe:duration-cn-base', isOpen && 'rotate-180')}
          />
        </button>
      </Heading>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            id={`${id}-panel`}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={collapseTransition(reduced)}
            className="overflow-hidden"
          >
            <div className={cx('text-cn-body text-cn-fg-secondary', card ? 'px-4 pb-4' : 'pb-3 pt-1')}>{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export interface AccordionItem {
  id: string;
  title: ReactNode;
  summary?: ReactNode;
  content: ReactNode;
  disabled?: boolean;
}

export interface AccordionProps {
  items: ReadonlyArray<AccordionItem>;
  /** `single` closes the others when one opens. Default `multiple`. */
  type?: 'single' | 'multiple';
  value?: ReadonlyArray<string>;
  defaultValue?: ReadonlyArray<string>;
  onValueChange?: (openIds: ReadonlyArray<string>) => void;
  level?: 2 | 3 | 4;
  className?: string;
}

/** A stack of Disclosures with dividers (FAQ, settings groups). */
export function Accordion({ items, type = 'multiple', value, defaultValue = [], onValueChange, level, className }: AccordionProps) {
  const [openIds, setOpenIds] = useControllableState<ReadonlyArray<string>>(value, defaultValue, onValueChange);
  const toggle = (id: string, next: boolean) => {
    if (type === 'single') setOpenIds(next ? [id] : []);
    else setOpenIds(next ? [...openIds, id] : openIds.filter((open) => open !== id));
  };
  return (
    <div className={cx('divide-y divide-cn-border rounded-cn-lg border border-cn-border bg-cn-surface', className)}>
      {items.map((item) => (
        <Disclosure
          key={item.id}
          title={item.title}
          summary={item.summary}
          disabled={item.disabled}
          level={level}
          open={openIds.includes(item.id)}
          onOpenChange={(next) => toggle(item.id, next)}
          variant="card"
          className="rounded-none border-0 bg-transparent"
        >
          {item.content}
        </Disclosure>
      ))}
    </div>
  );
}
