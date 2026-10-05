import type { MotionProps, Target, Transition } from 'framer-motion';

import { duration, easing } from './tokens';

type Bezier = [number, number, number, number];

const toBezier = (css: string): Bezier => (css.match(/-?[\d.]+/g) ?? []).map(Number) as Bezier;

/** The token easing curves in framer-motion's array form. */
export const ease = {
  out: toBezier(easing.out),
  in: toBezier(easing.in),
  inOut: toBezier(easing['in-out']),
} as const;

const seconds = (ms: number): number => ms / 1000;

export type MotionPresetName = 'fade' | 'rise' | 'pop' | 'sheet-right' | 'sheet-left' | 'sheet-bottom';

/** Spread onto a motion element: `<motion.div {...motionPreset('rise', reduced)} />`. */
export type MotionPreset = Required<Pick<MotionProps, 'initial' | 'animate' | 'exit' | 'transition'>>;

const PRESETS: Record<MotionPresetName, { from: Target; ms: number }> = {
  fade: { from: { opacity: 0 }, ms: duration.fast },
  rise: { from: { opacity: 0, y: 4 }, ms: duration.base },
  pop: { from: { opacity: 0, scale: 0.98, y: 4 }, ms: duration.base },
  'sheet-right': { from: { x: '100%' }, ms: duration.slow },
  'sheet-left': { from: { x: '-100%' }, ms: duration.slow },
  'sheet-bottom': { from: { y: '100%' }, ms: duration.slow },
};

/**
 * Enter and exit motion for a named preset. Under reduced motion every preset
 * becomes an instant state change, per 01-experience-principles §10.
 */
export function motionPreset(name: MotionPresetName, reduced: boolean): MotionPreset {
  if (reduced) {
    return { initial: false, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0 } };
  }
  const { from, ms } = PRESETS[name];
  // Where each animated property comes to rest: fully opaque, full size, no offset.
  const rest = Object.fromEntries(Object.keys(from).map((key) => [key, key === 'opacity' || key === 'scale' ? 1 : 0]));
  return {
    initial: from,
    animate: { ...rest, transition: { duration: seconds(ms), ease: ease.out } },
    exit: { ...from, transition: { duration: seconds(Math.min(ms, duration.fast)), ease: ease.in } },
    transition: { duration: seconds(ms), ease: ease.out },
  };
}

/** Height collapse and expand (steps folding to a summary). */
export function collapseTransition(reduced: boolean): Transition {
  return reduced ? { duration: 0 } : { duration: seconds(duration.base), ease: ease.inOut };
}
