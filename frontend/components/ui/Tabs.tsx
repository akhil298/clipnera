'use client';

import { motion } from 'framer-motion';
import { createContext, type KeyboardEvent, type ReactNode, useContext, useId } from 'react';

import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { ease } from '@/lib/design/motion';
import { cx, focusRing } from '@/lib/design/styles';
import { duration } from '@/lib/design/tokens';
import { useControllableState } from '@/lib/design/useControllableState';

interface TabsContextValue {
  baseId: string;
  value: string;
  select: (value: string) => void;
  variant: 'underline' | 'pill';
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabs(): TabsContextValue {
  const context = useContext(TabsContext);
  if (!context) throw new Error('Tab components must be inside <Tabs>');
  return context;
}

const tabId = (baseId: string, value: string) => `${baseId}-tab-${value}`;
const panelId = (baseId: string, value: string) => `${baseId}-panel-${value}`;

export interface TabsProps {
  value?: string;
  defaultValue: string;
  onValueChange?: (value: string) => void;
  /** `underline` for page sections (Settings); `pill` for panel switches (Steps / Changes). */
  variant?: 'underline' | 'pill';
  children: ReactNode;
  className?: string;
}

/**
 * Switches between views of one thing. WAI-ARIA tabs with automatic
 * activation: arrows move and select, Home/End jump, Tab goes into the panel.
 */
export function Tabs({ value, defaultValue, onValueChange, variant = 'underline', children, className }: TabsProps) {
  const baseId = useId();
  const [current, select] = useControllableState(value, defaultValue, onValueChange);
  return (
    <TabsContext.Provider value={{ baseId, value: current, select, variant }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabList({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  const { variant, select } = useTabs();

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]:not([disabled])'));
    const index = tabs.indexOf(document.activeElement as HTMLButtonElement);
    const moves: Record<string, number> = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1 };
    if (!(event.key in moves) || index < 0) return;
    event.preventDefault();
    const next = tabs[(moves[event.key] + tabs.length) % tabs.length];
    next.focus();
    if (next.dataset.value) select(next.dataset.value);
  };

  return (
    <div
      role="tablist"
      aria-label={label}
      aria-orientation="horizontal"
      onKeyDown={onKeyDown}
      className={cx(
        'flex items-center overflow-x-auto',
        variant === 'underline' ? 'gap-5 border-b border-cn-border' : 'gap-1 rounded-cn-md bg-cn-surface p-0.5',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Tab({ value, children, disabled }: { value: string; children: ReactNode; disabled?: boolean }) {
  const { baseId, value: current, select, variant } = useTabs();
  const reduced = useReducedMotion();
  const selected = current === value;
  const underline = variant === 'underline';

  return (
    <button
      type="button"
      role="tab"
      id={tabId(baseId, value)}
      aria-selected={selected}
      aria-controls={selected ? panelId(baseId, value) : undefined}
      tabIndex={selected ? 0 : -1}
      disabled={disabled}
      data-value={value}
      onClick={() => select(value)}
      className={cx(
        'relative inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap font-semibold transition-colors duration-cn-fast [&_svg]:size-4',
        'disabled:cursor-not-allowed disabled:opacity-50',
        underline ? 'h-10 text-cn-body' : 'h-8 rounded-cn-sm px-3 text-cn-label',
        selected ? 'text-cn-fg' : 'text-cn-fg-secondary hover:text-cn-fg',
        !underline && !selected && 'hover:bg-cn-surface-hover',
        focusRing,
      )}
    >
      {selected && (
        <motion.span
          aria-hidden
          layoutId={reduced ? undefined : `${baseId}-indicator`}
          transition={{ duration: duration.base / 1000, ease: ease.out }}
          className={cx(
            'absolute',
            underline ? 'inset-x-0 -bottom-px h-0.5 rounded-cn-full bg-cn-accent' : 'inset-0 rounded-cn-sm bg-cn-surface-active shadow-cn-1',
          )}
        />
      )}
      <span className="relative">{children}</span>
    </button>
  );
}

export function TabPanel({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  const { baseId, value: current } = useTabs();
  if (current !== value) return null;
  return (
    <div
      role="tabpanel"
      id={panelId(baseId, value)}
      aria-labelledby={tabId(baseId, value)}
      tabIndex={0}
      className={cx(focusRing, 'rounded-cn-xs focus-visible:outline-offset-4', className)}
    >
      {children}
    </div>
  );
}
