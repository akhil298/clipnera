'use client';

import { useRouter } from 'next/navigation';
import { type ChangeEvent, type DragEvent, useEffect, useRef, useState } from 'react';

import { savePendingUpload, savePendingUploadFile } from '@/components/home/handoff';
import { Chip, InlineAlert, PromptBar, useIsClient, type PromptContext } from '@/components/ui';
import { useReducedMotion } from '@/lib/design/useReducedMotion';
import { HERO_SUGGESTIONS } from '@/lib/marketing/content';
import { onHeroFocusRequest } from '@/lib/marketing/heroFocus';
import { savePendingPrompt } from '@/lib/marketing/pendingPrompt';
import { useSignedIn } from '@/lib/marketing/useSignedIn';
import { extractYoutubeVideoId, youtubeThumbnailUrl } from '@/lib/utils/urlParser';
import { formatBytes } from '@/lib/utils/videoFile';

const YOUTUBE_LINK = /(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com|youtu\.be)\/\S+/i;
const ANY_LINK = /(?:https?:\/\/|www\.)\S+/i;
const VIDEO_TYPES = /^video\//;
const UPLOAD_PATH = '/dashboard/upload';
/** Hides the Edit/Ask/Plan switch until PromptBar takes `modes={[]}` (DS-9): the landing always makes clips. */
const HIDE_MODES = '[&_[role=radiogroup]]:hidden';

type Issue = 'bad-link' | 'not-video' | 'offline' | 'storage';

const ISSUE_TEXT: Record<Issue, string> = {
  'bad-link': 'That isn’t a YouTube link. Paste a youtube.com or youtu.be address, or add the video file with the paperclip.',
  'not-video': 'That file isn’t a video. Use an MP4, MOV, WebM or MKV.',
  offline: 'You’re offline. Your prompt is kept on this page; send it when you’re back.',
  storage: 'This browser wouldn’t keep your prompt through sign-in, so copy it before you go.',
};

const loginFor = (next: string) => `/login?next=${next}`;

/**
 * The landing hero: paste a YouTube link, attach a video or type. Nothing runs
 * here. Send keeps the draft (sessionStorage `cn.pendingPrompt`, or the picked
 * file for the upload flow) and goes to Home, through sign-in when needed.
 */
export function HeroComposer() {
  const router = useRouter();
  const hydrated = useIsClient();
  const signedIn = useSignedIn();
  const reducedMotion = useReducedMotion();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [text, setText] = useState('');
  const [link, setLink] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [issue, setIssue] = useState<Issue | null>(null);
  const [dragging, setDragging] = useState(false);

  // `/editor?brief=…` and `/?prompt=…` pre-fill the bar (screens/01 §2 URLs).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const carried = params.get('prompt') ?? params.get('brief');
    if (carried) setText(carried.slice(0, 2000));
  }, []);

  useEffect(
    () =>
      onHeroFocusRequest(() => {
        document.getElementById('top')?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' });
        textareaRef.current?.focus({ preventScroll: true });
      }),
    [reducedMotion],
  );

  const onValueChange = (next: string) => {
    const youtube = next.match(YOUTUBE_LINK)?.[0];
    if (youtube && extractYoutubeVideoId(youtube)) {
      setLink(youtube.startsWith('http') ? youtube : `https://${youtube}`);
      setFile(null);
      setIssue(null);
      setText(next.replace(youtube, '').replace(/\s{2,}/g, ' ').trimStart());
      return;
    }
    setIssue(ANY_LINK.test(next) ? 'bad-link' : issue === 'bad-link' ? null : issue);
    setText(next);
  };

  const attach = (picked: File | undefined) => {
    if (!picked) return;
    if (!VIDEO_TYPES.test(picked.type)) return setIssue('not-video');
    setFile(picked);
    setLink(null);
    setIssue(null);
    textareaRef.current?.focus();
  };

  const send = async () => {
    if (issue === 'bad-link') return textareaRef.current?.focus();
    if (!navigator.onLine) return setIssue('offline');
    if (file) {
      // The upload flow picks the file up again; if storage refuses it, it simply asks for the file.
      savePendingUpload(text.trim());
      await savePendingUploadFile(file);
      router.push(signedIn ? UPLOAD_PATH : loginFor(UPLOAD_PATH));
      return;
    }
    if (!savePendingPrompt(text, link ?? undefined)) return setIssue('storage');
    router.push(signedIn ? '/dashboard' : loginFor('/dashboard'));
  };

  const videoId = link ? extractYoutubeVideoId(link) : null;
  const contexts: PromptContext[] = file
    ? [{ id: 'file', kind: 'asset', label: file.name, meta: formatBytes(file.size) }]
    : link && videoId
      ? [{ id: 'link', kind: 'asset', label: 'YouTube video', meta: videoId, thumbnailUrl: youtubeThumbnailUrl(link) }]
      : [];

  const isFileDrag = (event: DragEvent) => event.dataTransfer.types.includes('Files');

  return (
    <div className="flex w-full flex-col items-center gap-4">
      <div
        className="relative w-full max-w-2xl text-left"
        onDragOver={(event) => {
          if (!isFileDrag(event)) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
        }}
        onDrop={(event) => {
          if (!isFileDrag(event)) return;
          event.preventDefault();
          setDragging(false);
          attach(event.dataTransfer.files[0]);
        }}
      >
        <PromptBar
          ref={textareaRef}
          size="hero"
          value={text}
          onValueChange={onValueChange}
          onSubmit={send}
          mode="edit"
          onModeChange={() => undefined}
          contexts={contexts}
          onRemoveContext={() => {
            setLink(null);
            setFile(null);
          }}
          onAttach={() => fileRef.current?.click()}
          disabled={!hydrated}
          label="Paste a YouTube link or describe the clips you want"
          placeholder="Paste a YouTube link or drop a video, then say what you want"
          className={HIDE_MODES}
        />
        <input ref={fileRef} type="file" accept="video/*" hidden onChange={(event: ChangeEvent<HTMLInputElement>) => attach(event.target.files?.[0])} />
        {dragging && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-cn-2xl border-2 border-dashed border-cn-accent-border bg-cn-accent-subtle text-cn-body font-semibold text-cn-accent-text"
          >
            Drop video to start
          </div>
        )}
      </div>

      <div className="w-full max-w-2xl text-left">
        {issue ? (
          <InlineAlert tone={issue === 'offline' || issue === 'storage' ? 'warning' : 'danger'} live="alert">
            {ISSUE_TEXT[issue]}
          </InlineAlert>
        ) : (
          contexts.length > 0 &&
          !text.trim() && <p className="text-center text-cn-label text-cn-fg-secondary">Now say what you want, or pick a suggestion below.</p>
        )}
      </div>

      <div role="group" aria-label="Suggestions" className="flex max-w-2xl flex-wrap justify-center gap-2">
        {HERO_SUGGESTIONS.map((suggestion) => (
          <Chip
            key={suggestion}
            onClick={() => {
              setText(suggestion);
              textareaRef.current?.focus();
            }}
          >
            {suggestion}
          </Chip>
        ))}
      </div>
    </div>
  );
}
