'use client';

import { useEffect, useRef, useState } from 'react';

import { InlineAlert } from '@/components/ui';

import { takePendingPrompt } from './handoff';
import { HomeComposer } from './HomeComposer';
import { InProgressRow } from './InProgressRow';
import { ProjectSheet } from './ProjectSheet';
import { DEFAULT_INSTRUCTION, SUGGESTIONS } from './starters';
import { SuggestionChips } from './SuggestionChips';
import { useHomeProjects, useHomeUser } from './useHomeData';

const greetingFor = (hour: number) => (hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening');

/** Home: greeting, the hero composer, starters, what's running, then the project sheet. */
export function HomeScreen() {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState('');
  const [link, setLink] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);
  const [greeting, setGreeting] = useState('Welcome back');
  const firstName = useHomeUser().data?.name.trim().split(/\s+/)[0];
  const projects = useHomeProjects();

  useEffect(() => {
    // Time of day and session storage exist only in the browser; read them after mount so hydration matches.
    setGreeting(greetingFor(new Date().getHours()));
    const pending = takePendingPrompt();
    if (!pending) return;
    setText(pending.text || (pending.url ? DEFAULT_INSTRUCTION : ''));
    if (pending.url) setLink(pending.url);
    setRestored(true);
    textareaRef.current?.focus();
  }, []);

  const fill = (next: string) => {
    setText(next);
    textareaRef.current?.focus();
  };

  const applyTemplate = (prompt: string) => {
    fill(prompt);
    textareaRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  };

  const showChips = text.trim() === '' || text === DEFAULT_INSTRUCTION;

  return (
    <div className="flex flex-col gap-16 pt-8 md:pt-32 lg:pt-40">
      <section aria-labelledby="home-title" className="mx-auto flex w-full max-w-2xl flex-col items-center gap-4 px-4 text-center">
        <p className="text-cn-label text-cn-fg-muted">{firstName ? `${greeting}, ${firstName}` : greeting}</p>
        <h1 id="home-title" className="text-cn-display-sm font-bold text-cn-fg md:text-cn-display">
          What should we cut today?
        </h1>

        <div className="mt-2 flex w-full flex-col gap-2">
          {restored && (
            <InlineAlert live="status" onDismiss={() => setRestored(false)}>
              Kept from before you signed in. Nothing runs until you press send.
            </InlineAlert>
          )}
          <HomeComposer value={text} onValueChange={setText} link={link} onLinkChange={setLink} textareaRef={textareaRef} />
        </div>

        {showChips && <SuggestionChips items={link ? SUGGESTIONS.withVideo : SUGGESTIONS.noVideo} onPick={fill} />}
      </section>

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-4">
        {projects.items && <InProgressRow items={projects.items} />}
        <ProjectSheet
          items={projects.items}
          loading={projects.isPending}
          failed={projects.isError}
          onRetry={() => void projects.refetch()}
          onUseTemplate={applyTemplate}
        />
      </div>
    </div>
  );
}
