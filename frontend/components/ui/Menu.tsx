'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { Check } from 'lucide-react';
import { type KeyboardEvent, type ReactNode, type RefObject, useEffect, useId, useRef, useState } from 'react';

import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { useDismissOnOutsidePointer, useLayer } from '@/lib/design/layers';
import { motionPreset } from '@/lib/design/motion';
import { cx, floatingSurface } from '@/lib/design/styles';
import { type Align, type Side, useAnchoredPosition } from '@/lib/design/useAnchoredPosition';

import { Kbd } from './Kbd';
import { Portal } from './Portal';

export type MenuEntry =
  | {
      type?: 'item';
      id: string;
      label: string;
      icon?: ReactNode;
      /** Shortcut hint, e.g. `['⌘', 'D']`. Display only; wire the shortcut elsewhere. */
      shortcut?: readonly string[];
      /** Destructive actions are rose and go last, after a separator. */
      danger?: boolean;
      disabled?: boolean;
      /** Renders as a `menuitemcheckbox` with a tick. */
      checked?: boolean;
      onSelect: () => void;
    }
  | { type: 'separator'; id: string }
  | { type: 'label'; id: string; label: string };

type ActionEntry = Extract<MenuEntry, { onSelect: () => void }>;

export interface MenuTriggerProps {
  ref: RefObject<HTMLButtonElement | null>;
  id: string;
  'aria-haspopup': 'menu';
  'aria-expanded': boolean;
  'aria-controls': string | undefined;
  onClick: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
}

export interface MenuProps {
  /** Render the trigger (usually an IconButton or Button) and spread these props onto it. */
  trigger: (props: MenuTriggerProps) => ReactNode;
  items: ReadonlyArray<MenuEntry>;
  side?: Side;
  align?: Align;
  className?: string;
}

const isAction = (entry: MenuEntry): entry is ActionEntry => entry.type === undefined || entry.type === 'item';
const TYPEAHEAD_RESET_MS = 500;

/**
 * A list of actions on a trigger (clip "More" menu, account menu). Follows the
 * WAI-ARIA menu button pattern: arrows move, Home/End jump, typing a letter
 * jumps to a match, Enter/Space choose, Escape closes and returns focus.
 */
export function Menu({ trigger, items, side = 'bottom', align = 'start', className }: MenuProps) {
  const id = useId();
  const triggerId = `${id}-trigger`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const typeahead = useRef({ text: '', at: 0 });
  const [open, setOpen] = useState(false);
  /** Which item gets focus when the menu opens (a pointer open focuses the first, as the APG pattern does). */
  const [focusOnOpen, setFocusOnOpen] = useState<'first' | 'last'>('first');
  const reduced = useReducedMotion();
  const { style, ready } = useAnchoredPosition(open, triggerRef, panelRef, { side, align, offset: 6 });

  const actions = items.filter(isAction).filter((item) => !item.disabled);

  const close = (returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  };

  useLayer(open, () => close(true));
  useDismissOnOutsidePointer(open, [triggerRef, panelRef], () => close(false));

  const focusAt = (index: number) => {
    const item = actions[(index + actions.length) % actions.length];
    if (item) itemRefs.current.get(item.id)?.focus();
  };

  useEffect(() => {
    if (open && ready) focusAt(focusOnOpen === 'first' ? 0 : actions.length - 1);
    // Only once the open menu is placed; `actions` is derived from props and stable while open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, ready, focusOnOpen]);

  const openWith = (where: 'first' | 'last') => {
    setFocusOnOpen(where);
    setOpen(true);
  };

  const onTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openWith('first');
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      openWith('last');
    }
  };

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = actions.findIndex((item) => itemRefs.current.get(item.id) === document.activeElement);
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        focusAt(current + 1);
        return;
      case 'ArrowUp':
        event.preventDefault();
        focusAt(current - 1);
        return;
      case 'Home':
        event.preventDefault();
        focusAt(0);
        return;
      case 'End':
        event.preventDefault();
        focusAt(actions.length - 1);
        return;
      case 'Tab':
        close(false);
        return;
    }
    if (event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey) {
      const now = Date.now();
      const text = (now - typeahead.current.at > TYPEAHEAD_RESET_MS ? '' : typeahead.current.text) + event.key.toLowerCase();
      typeahead.current = { text, at: now };
      const ordered = [...actions.slice(current + 1), ...actions.slice(0, current + 1)];
      const match = ordered.find((item) => item.label.toLowerCase().startsWith(text));
      if (match) itemRefs.current.get(match.id)?.focus();
    }
  };

  const choose = (item: ActionEntry) => {
    close(true);
    item.onSelect();
  };

  const preset = motionPreset('rise', reduced);

  return (
    <>
      {trigger({
        ref: triggerRef,
        id: triggerId,
        'aria-haspopup': 'menu',
        'aria-expanded': open,
        'aria-controls': open ? id : undefined,
        onClick: () => (open ? close(false) : openWith('first')),
        onKeyDown: onTriggerKeyDown,
      })}
      <Portal>
        <AnimatePresence>
          {open && (
            <motion.div
              ref={panelRef}
              id={id}
              role="menu"
              aria-labelledby={triggerId}
              aria-orientation="vertical"
              style={style}
              onKeyDown={onMenuKeyDown}
              {...preset}
              className={cx('z-cn-popover min-w-48 max-w-[calc(100vw-16px)] p-1', floatingSurface, className)}
            >
              {items.map((entry) => {
                if (entry.type === 'separator') return <div key={entry.id} role="separator" className="-mx-1 my-1 h-px bg-cn-border" />;
                if (entry.type === 'label')
                  return (
                    <div key={entry.id} role="presentation" className="px-2.5 pb-1 pt-2 text-cn-caption font-semibold text-cn-fg-muted">
                      {entry.label}
                    </div>
                  );
                const checkable = entry.checked !== undefined;
                return (
                  <button
                    key={entry.id}
                    ref={(node) => {
                      if (node) itemRefs.current.set(entry.id, node);
                      else itemRefs.current.delete(entry.id);
                    }}
                    type="button"
                    role={checkable ? 'menuitemcheckbox' : 'menuitem'}
                    aria-checked={checkable ? entry.checked : undefined}
                    aria-disabled={entry.disabled || undefined}
                    tabIndex={-1}
                    onClick={() => !entry.disabled && choose(entry)}
                    onPointerMove={(event) => !entry.disabled && event.currentTarget.focus()}
                    className={cx(
                      'flex h-9 w-full items-center gap-2.5 rounded-cn-sm px-2.5 text-left text-cn-body outline-none [&_svg]:size-4',
                      'focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-cn-focus',
                      entry.disabled
                        ? 'cursor-not-allowed text-cn-fg-disabled'
                        : entry.danger
                          ? 'text-cn-danger-text focus:bg-cn-danger-subtle'
                          : 'text-cn-fg focus:bg-cn-surface-hover',
                    )}
                  >
                    {checkable ? (
                      <span aria-hidden className="inline-flex size-4 text-cn-accent-text">
                        {entry.checked && <Check />}
                      </span>
                    ) : (
                      entry.icon && (
                        <span aria-hidden className={cx('inline-flex', !entry.danger && 'text-cn-fg-secondary')}>
                          {entry.icon}
                        </span>
                      )
                    )}
                    <span className="flex-1 truncate">{entry.label}</span>
                    {/* Visual hint only, kept out of the item's name; the shortcut itself is announced where it is wired. */}
                    {entry.shortcut && (
                      <span aria-hidden className="ml-4 inline-flex">
                        <Kbd keys={entry.shortcut} />
                      </span>
                    )}
                  </button>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>
      </Portal>
    </>
  );
}
