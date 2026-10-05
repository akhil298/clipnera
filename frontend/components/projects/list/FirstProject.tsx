'use client';

import { Upload } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { buttonClasses, PromptBar, type PromptMode } from '@/components/ui';
import { extractYoutubeVideoId } from '@/lib/utils/urlParser';

const UPLOAD = '/dashboard/upload';

/** The first YouTube link in the text, and what the user asked for around it. */
function splitPrompt(text: string): { url: string | null; prompt: string } {
  const words = text.trim().split(/\s+/);
  const index = words.findIndex((word) => extractYoutubeVideoId(word));
  if (index < 0) return { url: null, prompt: text.trim() };
  return { url: words[index], prompt: words.filter((_, i) => i !== index).join(' ') };
}

/** Empty Projects page: the composer, not a dead end (research lovable-visual 13). */
export function FirstProject() {
  const router = useRouter();
  const [text, setText] = useState('');
  const [mode, setMode] = useState<PromptMode>('edit');
  const [needsVideo, setNeedsVideo] = useState(false);

  const submit = () => {
    const { url, prompt } = splitPrompt(text);
    if (!url) {
      setNeedsVideo(true);
      return;
    }
    const params = new URLSearchParams({ url });
    if (prompt) params.set('prompt', prompt);
    router.push(`${UPLOAD}?${params}`);
  };

  return (
    <section aria-labelledby="first-project" className="mx-auto flex w-full max-w-2xl flex-col items-center gap-6 py-12 text-center sm:py-20">
      <div className="flex flex-col gap-2">
        <h2 id="first-project" className="text-cn-title-lg font-semibold text-cn-fg">
          Your first project starts here
        </h2>
        <p className="text-cn-body text-cn-fg-secondary">
          Paste a YouTube link or add a video, say what you want, and Clipnera finds the moments worth posting. Each video becomes a project
          with its clips inside.
        </p>
      </div>
      <div className="flex w-full flex-col gap-2 text-left">
        {/* DS-9: PromptBar has no `modes` prop yet; with no project there is nothing to switch, so the switch is hidden. */}
        <PromptBar
          size="hero"
          label="Describe the clips you want"
          placeholder="Paste a YouTube link and say what you want, like “three funny moments under 40 seconds”"
          value={text}
          onValueChange={(value) => {
            setText(value);
            setNeedsVideo(false);
          }}
          onSubmit={submit}
          mode={mode}
          onModeChange={setMode}
          onAttach={() => router.push(UPLOAD)}
          className="[&_[role=radiogroup]]:hidden"
        />
        {needsVideo && (
          <p role="alert" className="px-2 text-cn-caption text-cn-danger-text">
            Add a video or paste a YouTube link first. Clipnera works from your footage.
          </p>
        )}
      </div>
      <Link href={UPLOAD} className={buttonClasses({ variant: 'ghost', size: 'md' })}>
        <Upload aria-hidden className="size-4" />
        Upload a video
      </Link>
    </section>
  );
}
