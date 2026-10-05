'use client';

import { motion } from 'framer-motion';

import { duration } from '@/lib/design/tokens';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

/**
 * Text that arrives in pieces (run.plan.delta, run.message.delta). Word groups
 * fade in over 120 ms; no caret block (01 §10). Under reduced motion only
 * finished sentences are shown, so the text appears sentence by sentence.
 */
export function StreamedText({ text, done = false, className }: { text: string; done?: boolean; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) {
    const sentences = done ? text : text.slice(0, Math.max(text.lastIndexOf('. '), text.lastIndexOf('.” ')) + 1);
    return <p className={className}>{sentences}</p>;
  }
  const groups = text.match(/(\S+\s*){1,3}/g) ?? [];
  return (
    <p className={className}>
      {groups.map((group, index) => (
        <motion.span
          // Groups only ever append, so the index is a stable key.
          key={index}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: duration.stream / 1000 }}
        >
          {group}
        </motion.span>
      ))}
    </p>
  );
}
