import { Sparkles } from 'lucide-react';

import type { PromptPreview } from './session';

const hostAndPath = (url: string) => {
  try {
    const { host, pathname, search } = new URL(url);
    return `${host.replace(/^www\./, '')}${pathname}${search}`;
  } catch {
    return url;
  }
};

/** The landing page's prompt, visibly waiting (07 §7): one line of preview, and the promise that nothing runs. */
export function KeptPromptNote({ prompt }: { prompt: PromptPreview }) {
  const preview = [prompt.text && `“${prompt.text}”`, prompt.url && hostAndPath(prompt.url)].filter(Boolean).join(' · ');
  return (
    <div className="flex items-start gap-2.5 rounded-cn-md border border-cn-border bg-cn-bg p-3 text-left">
      <Sparkles aria-hidden className="mt-0.5 size-4 shrink-0 text-cn-accent-text" />
      <div className="min-w-0 space-y-0.5">
        <p className="text-cn-label font-semibold text-cn-fg">Kept from before you signed in</p>
        <p className="truncate text-cn-caption text-cn-fg-secondary">{preview}</p>
        <p className="text-cn-caption text-cn-fg-muted">It’ll be waiting on Home. Nothing runs until you press send.</p>
      </div>
    </div>
  );
}
