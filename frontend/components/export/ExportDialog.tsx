'use client';

import { useQuery } from '@tanstack/react-query';
import { type FormEvent, type ReactNode, useId, useMemo, useState } from 'react';

import { Button, Dialog, Disclosure, SegmentedControl, SkeletonText } from '@/components/ui';
import { getEntitlements } from '@/lib/api/credits';
import { socialExportRequest } from '@/lib/api/export/request';
import type { ExportLookOptions, ExportRenderOptions } from '@/lib/api/export/types';
import { getCreatorIntro } from '@/lib/api/pipeline';
import { creditKeys } from '@/lib/query/keys/credits';
import { uploadKeys } from '@/lib/query/keys/upload';
import { getCaptionStyle, resolveCaptionPreset } from '@/lib/utils/captionStyles';
import { formatBytes, formatDuration } from '@/lib/utils/videoFile';

import { ExportLookFields, type LookLocks } from './ExportLookFields';
import {
  cardAspect,
  DEFAULT_RENDER,
  estimateBytes,
  type ExportClip,
  type ExportScope,
  type ExportSource,
  FRAME_RATE_LABEL,
  HONOURED,
  outputSize,
  QUALITY_LABEL,
  ratioLabel,
  renderMeta,
  scopeChoices,
  sourceLook,
  sourceRatio,
  sourceSeconds,
} from './source';
import { type ExportRequestPlan, startExport } from './store';

export interface ExportDialogProps {
  source: ExportSource;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the new job's id once the export has started (the dialog has closed). */
  onStarted?: (jobId: string) => void;
}

/**
 * Export (editor §11.1, 07 §6.6): "Video file", resolution, what the video carries, a collapsed
 * Advanced section, then duration and estimated size above "Export video". Submitting closes the
 * dialog at once and a render card takes over.
 */
export function ExportDialog(props: ExportDialogProps) {
  // A fresh form every time it opens, so the choices start from the source's saved look.
  const [session, setSession] = useState(0);
  const [wasOpen, setWasOpen] = useState(props.open);
  if (props.open !== wasOpen) {
    setWasOpen(props.open);
    if (props.open) setSession((n) => n + 1);
  }
  return <ExportForm key={session} {...props} />;
}

function ExportForm({ source, open, onOpenChange, onStarted }: ExportDialogProps) {
  const formId = useId();
  const entitlements = useQuery({
    queryKey: creditKeys.entitlements(),
    queryFn: ({ signal }) => getEntitlements(signal),
    enabled: open,
  });
  const introOnPlan = entitlements.data?.creator_intro ?? false;
  const intro = useQuery({
    queryKey: uploadKeys.creatorIntro(),
    queryFn: ({ signal }) => getCreatorIntro(signal),
    enabled: open && introOnPlan,
  });

  const scopes = useMemo(() => (source.kind === 'clips' ? scopeChoices(source) : []), [source]);
  const [scope, setScope] = useState<ExportScope>(scopes[0]?.value ?? 'all');
  const clips: readonly ExportClip[] = scopes.find((choice) => choice.value === scope)?.clips ?? [];

  const look = sourceLook(source, source.kind === 'clips' ? (scopes[0]?.clips ?? []) : []);
  const [render, setRender] = useState<ExportRenderOptions>(DEFAULT_RENDER);
  const [lookOptions, setLookOptions] = useState<ExportLookOptions>({
    burn_subtitles: look.burn_subtitles ?? true,
    show_title: look.show_title ?? true,
    watermark_enabled: look.watermark_enabled ?? true,
    channel_intro: true,
  });

  const locks: LookLocks = {
    watermarkForced: entitlements.data?.watermark_forced ?? false,
    introOnPlan,
    introReady: intro.data?.status === 'ready' && intro.data.enabled,
  };

  const title = source.kind === 'editor' ? source.title : clips.length === 1 ? clips[0].title || 'Untitled clip' : `${clips.length} clips`;
  const seconds = sourceSeconds(source, clips);
  const ratio = sourceRatio(source, look);
  const size = outputSize(ratio, render.resolution);
  const files = source.kind === 'clips' ? clips.length : 1;
  const bundle = files > 1;
  const styleName = look.caption_config?.preset ? getCaptionStyle(resolveCaptionPreset(look.caption_config.preset)).name : undefined;

  // Each exported clip counts toward the plan's daily export limit (pipeline/service.py export_for_social).
  const dailyLimit = entitlements.data?.daily_limits.exports ?? null;
  const exportsLeft = dailyLimit === null ? null : Math.max(0, dailyLimit - (entitlements.data?.usage_today.exports ?? 0));
  const overLimit = exportsLeft !== null && files > exportsLeft;
  const canSubmit = files > 0 && !overLimit && !entitlements.isPending;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    const effective: ExportLookOptions = {
      ...lookOptions,
      show_title: lookOptions.burn_subtitles && lookOptions.show_title,
      watermark_enabled: locks.watermarkForced || lookOptions.watermark_enabled,
      channel_intro: locks.introOnPlan && locks.introReady && lookOptions.channel_intro,
    };
    const plan: ExportRequestPlan =
      source.kind === 'clips'
        ? {
            kind: 'blocking',
            projectId: source.projectId,
            body: socialExportRequest({
              clip_ids: clips.map((clip) => clip.id),
              bundle,
              look: { ...look, ...effective },
            }),
          }
        : {
            kind: 'job',
            body: {
              source: {
                type: 'editor_project',
                id: source.projectId,
                version_id: source.version,
              },
              options: { ...render, ...effective, bundle: false },
            },
          };
    const id = startExport({
      projectId: source.projectId,
      title,
      meta: renderMeta(seconds, files, size, render.resolution),
      poster: clips[0]?.poster_url ?? undefined,
      aspect: cardAspect(ratio),
      clipId: clips.length === 1 ? clips[0].id : undefined,
      bundle,
      plan,
    });
    onOpenChange(false);
    onStarted?.(id);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Export"
      description={`${title} · ${formatDuration(seconds)} · ${ratioLabel(ratio)}`}
      size="md"
      footer={
        <div className="flex w-full flex-col gap-3">
          <p className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted" aria-live="polite">
            {bundle ? `1 ZIP of ${files} videos` : '1 file'} · {formatDuration(seconds)} · about {formatBytes(estimateBytes(seconds, render.resolution))}
            {exportsLeft !== null && ` · ${exportsLeft} ${exportsLeft === 1 ? 'export' : 'exports'} left today`}
          </p>
          {overLimit && (
            <p role="alert" className="text-cn-caption text-cn-danger-text">
              {exportsLeft === 0 ? 'You’ve used today’s exports. More tomorrow.' : `Only ${exportsLeft} left today. Pick fewer clips.`}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" form={formId} disabled={!canSubmit}>
              Export video
            </Button>
          </div>
        </div>
      }
    >
      <form id={formId} onSubmit={submit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <p className="text-cn-label font-semibold text-cn-fg">Video file</p>
          {scopes.length > 1 && (
            <SegmentedControl
              label="Which clips"
              value={scope}
              onValueChange={setScope}
              options={scopes.map((choice) => ({
                value: choice.value,
                label: choice.label,
              }))}
            />
          )}
        </div>

        <Labeled label="Resolution">
          <SegmentedControl
            label="Resolution"
            value={render.resolution}
            onValueChange={(resolution) => setRender({ ...render, resolution })}
            options={[
              { value: '1080', label: '1080p' },
              {
                value: '720',
                label: '720p · faster',
                disabled: !HONOURED.resolution.includes('720'),
                ariaLabel: '720p, not available yet',
              },
              {
                value: '2160',
                label: '4K',
                disabled: !HONOURED.resolution.includes('2160'),
                ariaLabel: '4K, not available yet',
              },
            ]}
          />
          <p className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">
            {size.width}×{size.height}
          </p>
        </Labeled>

        {entitlements.isError && (
          <p className="text-cn-caption text-cn-fg-muted">Couldn’t check your plan, so the server applies its limits when you export.</p>
        )}
        {entitlements.isPending ? (
          <SkeletonText lines={4} />
        ) : (
          <ExportLookFields value={lookOptions} onChange={setLookOptions} locks={locks} styleName={lookOptions.burn_subtitles ? styleName : undefined} />
        )}

        <Disclosure
          title="Advanced"
          summary={`${render.format.toUpperCase()} · ${FRAME_RATE_LABEL[render.frame_rate]} · ${QUALITY_LABEL[render.quality]} quality`}
        >
          <div className="flex flex-col gap-4">
            <Labeled label="Frame rate">
              <SegmentedControl
                label="Frame rate"
                value={render.frame_rate}
                onValueChange={(frame_rate) => setRender({ ...render, frame_rate })}
                options={(['source', '30', '60'] as const).map((value) => ({
                  value,
                  label: FRAME_RATE_LABEL[value],
                  disabled: !HONOURED.frame_rate.includes(value),
                }))}
              />
            </Labeled>
            <Labeled label="Quality">
              <SegmentedControl
                label="Quality"
                value={render.quality}
                onValueChange={(quality) => setRender({ ...render, quality })}
                options={(['standard', 'high'] as const).map((value) => ({
                  value,
                  label: QUALITY_LABEL[value],
                  disabled: !HONOURED.quality.includes(value),
                }))}
              />
            </Labeled>
            <Labeled label="Format">
              <SegmentedControl label="Format" value={render.format} options={[{ value: 'mp4', label: 'MP4 (H.264)' }]} />
            </Labeled>
            <p className="text-cn-caption text-cn-fg-muted">Clipnera renders 1080p MP4 at the source frame rate for now.</p>
          </div>
        </Disclosure>
      </form>
    </Dialog>
  );
}

function Labeled({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <p aria-hidden className="text-cn-label font-semibold text-cn-fg">
        {label}
      </p>
      {children}
    </div>
  );
}
