'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { useOnline } from '@/components/home/useOnline';
import { useYoutubeSource } from '@/components/home/useYoutubeSource';
import { useToast } from '@/components/ui';
import { getEntitlements } from '@/lib/api/credits';
import { importYoutube, runCreditCost, type PipelineStartRequest } from '@/lib/api/pipeline';
import { listFolders, moveProjects, renameProject } from '@/lib/api/projects';
import { useConfig, useFlag } from '@/lib/flags/useFlag';
import { creditKeys } from '@/lib/query/keys/credits';
import { homeKeys } from '@/lib/query/keys/home';
import { projectKeys } from '@/lib/query/keys/projects';
import { isVideoContentType, sourceVideoUpload } from '@/lib/upload/sourceVideo';
import { onUploadSettled, resumeUpload, startUpload } from '@/lib/upload/store';
import { extractYoutubeVideoId } from '@/lib/utils/urlParser';
import { readVideoDuration, titleFromFileName } from '@/lib/utils/videoFile';

import { takeUploadHandoff } from './handoff';
import { DEFAULT_OPTIONS, toRunRequest, type RunOptions } from './options';

export interface PickedFile {
  file: File;
  /** null when the browser can't read the length; the server reads it after the upload. */
  duration: number | null;
}

const minutes = (seconds: number) => {
  const total = Math.round(seconds / 60);
  return total >= 60 ? `${Math.floor(total / 60)} h ${total % 60} min` : `${total} min`;
};

/**
 * Everything the New video form knows and does, shared by the dialog and the
 * full page: the source, the prompt, name, folder, options, the exact cost,
 * every reason Make clips is blocked, and the start itself.
 */
export function useNewVideo(onStarted: (projectId: string) => void) {
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const online = useOnline();
  const uploadsOn = useFlag('video_upload');
  const brollAllowed = useFlag('broll_studio.cutaways');
  const maxBytes = useConfig('uploads.max_bytes');

  const entitlements = useQuery({ queryKey: creditKeys.entitlements(), queryFn: ({ signal }) => getEntitlements(signal) });
  // NEEDS-BACKEND (API-7): no /folders yet, so the field stays hidden until this answers.
  const folders = useQuery({ queryKey: projectKeys.folders(), queryFn: ({ signal }) => listFolders(signal), retry: false });

  const [link, setLink] = useState('');
  const [picked, setPicked] = useState<PickedFile | null>(null);
  const [reading, setReading] = useState(false);
  const [fileIssue, setFileIssue] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [title, setTitle] = useState<string | null>(null);
  const [folderId, setFolderId] = useState<string | null>(null);
  const [options, setOptions] = useState<RunOptions>(DEFAULT_OPTIONS);

  const trimmedLink = link.trim();
  const youtubeUrl = !picked && extractYoutubeVideoId(trimmedLink) ? trimmedLink : null;
  const youtube = useYoutubeSource(youtubeUrl);

  const pickFile = async (file: File) => {
    setPicked(null);
    setFileIssue(null);
    if (!isVideoContentType(file.type)) return setFileIssue('Use an MP4, MOV, WebM or MKV video.');
    if (file.size > maxBytes) return setFileIssue(`Videos can be up to ${Math.floor(maxBytes / 1024 ** 3)} GB.`);
    setReading(true);
    const duration = await readVideoDuration(file);
    setReading(false);
    setPicked({ file, duration });
  };

  const clearSource = () => {
    setPicked(null);
    setFileIssue(null);
    setLink('');
    setTitle(null);
  };

  const handedOff = useRef(false);
  useEffect(() => {
    if (handedOff.current) return;
    handedOff.current = true;
    void takeUploadHandoff(new URLSearchParams(params.toString())).then((handoff) => {
      if (handoff.prompt) setPrompt(handoff.prompt.slice(0, 500));
      if (handoff.file) void pickFile(handoff.file);
      else if (handoff.url) setLink(handoff.url);
    });
    // Once per mount: the handoff is consumed as it is read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const plan = entitlements.data;
  const sourceTitle = picked ? titleFromFileName(picked.file.name) : youtube.data?.title ?? '';
  // The server stores whole seconds (ceil for uploads), and charges from that.
  const rawDuration = picked ? picked.duration : youtube.data?.duration_seconds || null;
  const duration = rawDuration ? Math.ceil(rawDuration) : null;
  const cost = plan && duration ? runCreditCost(plan, duration, options.formats.length) : null;
  const balance = plan?.credit_minutes_remaining ?? null;
  const maxSeconds = plan?.max_upload_duration_seconds ?? null;

  const linkIssue =
    !picked && trimmedLink && !youtubeUrl
      ? 'That isn’t a YouTube video link. Try one like youtube.com/watch?v=…'
      : youtube.isError
        ? 'I couldn’t check that link. Make sure the video is public, then paste it again.'
        : null;
  const tooLong =
    duration && maxSeconds && duration > maxSeconds
      ? `This video is ${minutes(duration)}. Your plan takes up to ${minutes(maxSeconds)} per video.`
      : null;
  const shortOfCredits = cost !== null && balance !== null && cost > balance;
  const checking = youtube.isPending && youtubeUrl !== null;
  const hasSource = picked !== null || (youtubeUrl !== null && youtube.isSuccess);

  const start = useMutation({
    // The server owns the run from here: YouTube is charged now and started when the download lands;
    // an upload carries the run in `complete`, so only the bytes need this tab.
    mutationFn: async (run: PipelineStartRequest) => {
      if (picked) {
        const task = await startUpload(sourceVideoUpload, picked.file, { durationSeconds: picked.duration, run });
        watchUpload(task.id);
        return task.targetId!;
      }
      const project = await importYoutube(youtubeUrl!, run, crypto.randomUUID());
      return project.id;
    },
    onSuccess: (projectId) => {
      const name = title?.trim();
      // NEEDS-BACKEND (API-6): PATCH /clips/projects/{id} and POST /projects/move; until then the
      // project keeps the video's own title and no folder, and the start is not held up.
      if (name && name !== sourceTitle) void renameProject(projectId, name).catch(() => undefined);
      if (folderId) void moveProjects([projectId], folderId).catch(() => undefined);
      void queryClient.invalidateQueries({ queryKey: creditKeys.entitlements() });
      void queryClient.invalidateQueries({ queryKey: projectKeys.all });
      void queryClient.invalidateQueries({ queryKey: homeKeys.projects() });
      onStarted(projectId);
    },
  });

  function watchUpload(taskId: string) {
    // Failure is told wherever the person is now; the toast host lives in the shell, not this form.
    onUploadSettled(taskId, (task) => {
      if (task?.phase !== 'failed') return;
      toast.show({
        tone: 'danger',
        title: `${task.name} didn’t finish`,
        description: task.error ?? 'Try again in a moment.',
        duration: null,
        action: {
          label: 'Try again',
          onClick: () => {
            resumeUpload(taskId);
            watchUpload(taskId);
          },
        },
      });
    });
  }

  const canStart = hasSource && !!plan && online && !tooLong && !shortOfCredits && !reading && !start.isPending;

  return {
    uploadsOn,
    brollAllowed,
    maxBytes,
    entitlements,
    folders,
    link,
    setLink: (value: string) => {
      setLink(value);
      setTitle(null);
    },
    picked,
    reading,
    pickFile,
    fileIssue,
    setFileIssue,
    clearSource,
    youtubeUrl,
    youtube,
    checking,
    linkIssue,
    tooLong,
    prompt,
    setPrompt,
    title: title ?? sourceTitle,
    setTitle,
    folderId,
    setFolderId,
    options,
    setOptions,
    duration,
    cost,
    balance,
    shortOfCredits,
    online,
    hasSource,
    canStart,
    start,
    submit: () => {
      if (canStart) start.mutate(toRunRequest(options, prompt, brollAllowed));
    },
  };
}

export type NewVideo = ReturnType<typeof useNewVideo>;
