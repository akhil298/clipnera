'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FolderOpen, Link2, Palette, Upload } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type DragEvent, type RefObject, useState } from 'react';

import { Button, ChoiceCard, CommandMenu, InlineAlert, PromptBar, buttonClasses, useIsClient, type CommandGroup, type PromptContext } from '@/components/ui';
import { estimateVideoCredits } from '@/hooks/useEntitlements';
import { homeApi, startClipsWhenReady, type HomeClipSettings } from '@/lib/api/home';
import { isPlanError } from '@/lib/api/errors';
import { spokenDuration } from '@/lib/design/timecode';
import { useFlag } from '@/lib/flags/useFlag';
import { homeKeys } from '@/lib/query/keys/home';
import { extractYoutubeVideoId } from '@/lib/utils/urlParser';

import { savePendingUpload, savePendingUploadFile } from './handoff';
import { projectHref } from './projectState';
import { DEFAULT_INSTRUCTION, LENGTH_CHOICES, MENTIONS_LENGTH, type LengthChoiceId } from './starters';
import { useHomeEntitlements } from './useHomeData';
import { useOnline } from './useOnline';
import { useYoutubeSource } from './useYoutubeSource';

const YOUTUBE_LINK = /(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com|youtu\.be)\/\S+/i;
const VIDEO_TYPES = /^video\//;
const UPLOAD_PATH = '/dashboard/upload';
const BILLING_PATH = '/dashboard/settings/billing';
/** Hides the Edit/Ask/Plan switch until PromptBar takes `modes={[]}` (DS-9): Home always makes clips. */
const HIDE_MODES = '[&_[role=radiogroup]]:hidden';

type Issue = 'need-video' | 'checking' | 'wrong-type';

const ISSUE_TEXT: Record<Issue, string> = {
  'need-video': 'Add a video or paste a YouTube link first. Clipnera works from your footage.',
  checking: 'I’m still checking the link. Send again in a moment.',
  'wrong-type': 'That file isn’t a video. Use an MP4, MOV, WebM or MKV.',
};

interface StartRequest {
  url: string;
  settings: HomeClipSettings;
  idempotencyKey: string;
}

export interface HomeComposerProps {
  value: string;
  onValueChange: (value: string) => void;
  /** The attached YouTube link; one video per prompt. */
  link: string | null;
  onLinkChange: (link: string | null) => void;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}

/**
 * The hero composer: paste a link, attach or drop a file, say what you want.
 * The cost shows before anything is spent, and one question about clip length
 * comes before credits are charged when the prompt doesn't answer it.
 */
export function HomeComposer({ value, onValueChange, link, onLinkChange, textareaRef }: HomeComposerProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const hydrated = useIsClient();
  const online = useOnline();
  const uploadsOn = useFlag('video_upload');
  const brollOn = useFlag('broll_studio.cutaways');
  const source = useYoutubeSource(link);
  const entitlements = useHomeEntitlements().data;

  const [issue, setIssue] = useState<Issue | null>(null);
  const [asking, setAsking] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [dragging, setDragging] = useState(false);

  const start = useMutation({
    mutationFn: async ({ url, settings, idempotencyKey }: StartRequest) => {
      const project = await homeApi.createFromYoutube(url, idempotencyKey);
      // The project page reads the run's state from the server, so a failed start shows there.
      startClipsWhenReady(project.id, settings).catch(() => undefined);
      return project;
    },
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: homeKeys.projects() });
      router.push(projectHref(project.id));
    },
  });

  const meta = source.data;
  const duration = meta?.duration_seconds ?? 0;
  const cost = meta && entitlements && duration > 0 ? estimateVideoCredits(entitlements, duration, 1) : undefined;
  const maxSeconds = entitlements?.max_upload_duration_seconds ?? 0;
  const tooLong = maxSeconds > 0 && duration > maxSeconds;
  const shortOfCredits = cost !== undefined && entitlements !== undefined && cost > entitlements.credit_minutes_remaining;

  const resetFeedback = () => {
    setIssue(null);
    setAsking(false);
    start.reset();
  };

  const attachLink = (url: string) => {
    onLinkChange(url);
    resetFeedback();
  };

  const changeText = (next: string) => {
    const match = next.match(YOUTUBE_LINK)?.[0];
    if (match && extractYoutubeVideoId(match)) {
      attachLink(match);
      onValueChange(next.replace(match, '').replace(/\s{2,}/g, ' ').trimStart() || DEFAULT_INSTRUCTION);
      return;
    }
    onValueChange(next);
    if (issue) setIssue(null);
  };

  const run = (lengthId: LengthChoiceId | 'skip') => {
    if (!link) return;
    const length = LENGTH_CHOICES.find((choice) => choice.id === lengthId);
    start.mutate({
      url: link,
      idempotencyKey: crypto.randomUUID(),
      settings: {
        caption_script: 'auto',
        broll: brollOn,
        ...(length ? { min_clip_duration: length.min, max_clip_duration: length.max } : {}),
      },
    });
  };

  const send = () => {
    if (!link) return setIssue('need-video');
    if (source.isPending) return setIssue('checking');
    if (source.isError || tooLong || shortOfCredits || start.isPending) return;
    if (MENTIONS_LENGTH.test(value)) return run('skip');
    setAsking(true);
  };

  const goToUpload = () => {
    savePendingUpload(value === DEFAULT_INSTRUCTION ? '' : value);
    router.push(UPLOAD_PATH);
  };

  const pasteLink = async () => {
    try {
      const text = await navigator.clipboard.readText();
      const match = text.match(YOUTUBE_LINK)?.[0];
      if (match && extractYoutubeVideoId(match)) {
        attachLink(match);
        if (!value.trim()) onValueChange(DEFAULT_INSTRUCTION);
        return;
      }
    } catch {
      // Clipboard access refused: the person pastes into the box instead.
    }
    textareaRef.current?.focus();
  };

  const menuGroups: CommandGroup[] = [
    {
      id: 'video',
      label: 'Add a video',
      items: [
        ...(uploadsOn
          ? [{ id: 'upload', label: 'Upload a video', description: 'MP4, MOV, WebM or MKV', icon: <Upload />, keywords: ['file', 'computer'], onSelect: goToUpload }]
          : []),
        { id: 'paste', label: 'Paste a YouTube link', description: 'From your clipboard, or paste it into the box', icon: <Link2 />, keywords: ['url', 'youtube'], onSelect: () => void pasteLink() },
      ],
    },
    {
      id: 'go',
      label: 'Go to',
      items: [
        { id: 'library', label: 'Library', description: 'Footage and B-roll you can use', icon: <FolderOpen />, onSelect: () => router.push('/dashboard/library') },
        { id: 'brand', label: 'Brand kit', description: 'Colours, logo and caption style', icon: <Palette />, onSelect: () => router.push('/dashboard/brand-kit') },
      ],
    },
  ];

  const isFileDrag = (event: DragEvent) => uploadsOn && event.dataTransfer.types.includes('Files');

  const onDrop = async (event: DragEvent<HTMLDivElement>) => {
    if (!isFileDrag(event)) return;
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (!file || !VIDEO_TYPES.test(file.type)) return setIssue('wrong-type');
    // If the browser refuses to keep the file, the upload flow simply asks for it again.
    await savePendingUploadFile(file);
    goToUpload();
  };

  const context: PromptContext[] = link
    ? [
        {
          id: 'source',
          kind: 'asset',
          label: meta?.title ?? (source.isError ? 'YouTube link' : 'Checking the link'),
          meta: meta?.duration_formatted,
          thumbnailUrl: meta?.thumbnail_url,
        },
      ]
    : [];

  return (
    <div className="flex w-full flex-col gap-3 text-left">
      <div
        className="relative"
        onDragOver={(event) => {
          if (!isFileDrag(event)) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
        }}
        onDrop={onDrop}
      >
        <PromptBar
          ref={textareaRef}
          size="hero"
          value={value}
          onValueChange={changeText}
          onSubmit={send}
          mode="edit"
          onModeChange={() => undefined}
          contexts={context}
          onRemoveContext={() => {
            onLinkChange(null);
            resetFeedback();
          }}
          onAttach={() => setMenuOpen(true)}
          creditCost={online ? cost : undefined}
          disabled={!hydrated || !online || start.isPending}
          label="Describe the clips you want"
          placeholder={link ? 'What should Clipnera make from this video?' : 'Paste a YouTube link or drop a video, then say what you want'}
          className={HIDE_MODES}
        />
        {dragging && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-cn-2xl border-2 border-dashed border-cn-accent-border bg-cn-accent-subtle text-cn-body font-semibold text-cn-accent-text"
          >
            Drop video to start
          </div>
        )}
      </div>

      <ComposerFeedback
        online={online}
        issue={issue === 'checking' && !source.isPending ? null : issue}
        startError={start.error}
        onRetry={() => start.variables && start.mutate(start.variables)}
        linkError={source.isError}
        tooLong={tooLong ? { duration, maxSeconds } : null}
        shortOfCredits={shortOfCredits && cost !== undefined && entitlements ? { duration, cost, remaining: entitlements.credit_minutes_remaining } : null}
      />

      {start.isPending && (
        <p role="status" className="text-cn-label text-cn-fg-secondary">
          Creating the project. I’ll take you to its progress page.
        </p>
      )}

      {asking && !start.isPending && (
        <div className="flex flex-col gap-2">
          {cost !== undefined && entitlements && (
            <p className="text-cn-label text-cn-fg-secondary">
              This uses about <span className="font-cn-mono tabular-nums">{cost}</span> credits; you’ll have{' '}
              <span className="font-cn-mono tabular-nums">{entitlements.credit_minutes_remaining - cost}</span> left. Nothing is charged until you pick.
            </p>
          )}
          <ChoiceCard
            question="How long should each clip be?"
            choices={LENGTH_CHOICES}
            onChoose={(id) => run(id as LengthChoiceId)}
            onSkip={() => run('skip')}
            skipLabel="Let Clipnera decide"
          />
          <Button variant="ghost" size="sm" className="self-start" onClick={() => setAsking(false)}>
            Not yet
          </Button>
        </div>
      )}

      <CommandMenu
        open={menuOpen}
        onOpenChange={setMenuOpen}
        groups={menuGroups}
        onSelect={() => undefined}
        label="Add to your prompt"
        placeholder="Search: upload, link, library…"
        emptyText="Nothing matches. Paste a YouTube link into the box instead."
      />
    </div>
  );
}

interface FeedbackProps {
  online: boolean;
  issue: Issue | null;
  startError: Error | null;
  onRetry: () => void;
  linkError: boolean;
  tooLong: { duration: number; maxSeconds: number } | null;
  shortOfCredits: { duration: number; cost: number; remaining: number } | null;
}

/** At most one line under the box, the most urgent first. Text and video always stay. */
function ComposerFeedback({ online, issue, startError, onRetry, linkError, tooLong, shortOfCredits }: FeedbackProps) {
  if (!online) {
    return <InlineAlert live="status">You’re offline. Your prompt is kept; send it when you’re back.</InlineAlert>;
  }
  if (startError) {
    const planLimit = isPlanError(startError);
    return (
      <InlineAlert
        tone="danger"
        live="alert"
        title="I couldn’t start this project"
        action={
          planLimit ? (
            <Link href={BILLING_PATH} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
              See plans
            </Link>
          ) : (
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Try again
            </Button>
          )
        }
      >
        {planLimit ? startError.message : 'Nothing was charged. Your prompt and video are still here.'}
      </InlineAlert>
    );
  }
  if (linkError) {
    return (
      <InlineAlert tone="danger" live="alert">
        I couldn’t read that link. Check it’s a public YouTube video, or try another.
      </InlineAlert>
    );
  }
  if (tooLong) {
    return (
      <InlineAlert
        tone="danger"
        live="alert"
        action={
          <Link href={BILLING_PATH} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
            See plans
          </Link>
        }
      >
        This video is {spokenDuration(tooLong.duration)}. Your plan takes up to {spokenDuration(tooLong.maxSeconds)} per video.
      </InlineAlert>
    );
  }
  if (shortOfCredits) {
    return (
      <InlineAlert
        tone="danger"
        live="alert"
        action={
          <Link href={BILLING_PATH} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
            Add credits
          </Link>
        }
      >
        This {Math.max(1, Math.round(shortOfCredits.duration / 60))}-minute video needs about {shortOfCredits.cost} credits; you have {shortOfCredits.remaining}. Your
        prompt and video stay here.
      </InlineAlert>
    );
  }
  if (issue) {
    return (
      <InlineAlert tone={issue === 'checking' ? 'neutral' : 'danger'} live={issue === 'checking' ? 'status' : 'alert'}>
        {ISSUE_TEXT[issue]}
      </InlineAlert>
    );
  }
  return null;
}
