'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type CopyState = 'idle' | 'copied' | 'failed';

const RESET_MS = 2000;

/** Copies text and reports the result for 2 s, so a button can say "Copied" or ask for a manual copy. */
export function useCopyToClipboard(): { state: CopyState; copy: (text: string) => Promise<boolean> } {
  const [state, setState] = useState<CopyState>('idle');
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = useCallback(async (text: string) => {
    clearTimeout(timer.current);
    let copied = true;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      copied = false;
    }
    setState(copied ? 'copied' : 'failed');
    timer.current = setTimeout(() => setState('idle'), RESET_MS);
    return copied;
  }, []);

  return { state, copy };
}
