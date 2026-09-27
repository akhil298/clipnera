"use client";
import React from 'react';
import { XCircle, RotateCcw } from 'lucide-react';
import { PipelineStep } from '@/lib/types';

interface PipelineStepIndicatorProps {
  steps: PipelineStep[];
  onRevert?: (step: string) => void;
}

const STEP_LABELS: Record<string, string> = {
  download: 'Download Video',
  audio_extraction: 'Extract Audio',
  ai_noise_cancellation: 'AI Noise Cancellation',
  transcription: 'Transcription',
  topic_research: 'Topic Research',
  visual_analysis: 'Visual Analysis',
  content_classification: 'Content Classification',
  highlight_detection: 'Highlight Detection',
  bounding_box_detection: 'Bounding Box Detection',
  scoring: 'Clip Scoring',
  metadata_generation: 'Clip Metadata',
  aspect_ratio_render: 'Aspect Ratio & Tracking',
  auto_reframe: 'Aspect Ratio & Tracking',
  clip_generation: 'Clip Generation',
  caption_styling: 'Caption Styling',
  export: 'Export',
};

export const PipelineStepIndicator: React.FC<PipelineStepIndicatorProps> = ({ steps, onRevert }) => {
  if (!steps || steps.length === 0) return null;

  const finished = steps.filter((s) => s.status === 'completed' || s.status === 'skipped').length;
  const running = steps.find((s) => s.status === 'running');
  const attentionSteps = steps.filter((s) => s.status === 'failed' || s.status === 'reverted');
  const hasFailure = attentionSteps.some((s) => s.status === 'failed');
  const needsAttention = attentionSteps.length > 0;

  // Once every step has landed cleanly the tracker has nothing left to say, and
  // it pushes the clips it was reporting on below the fold. A run that failed or
  // has a reverted step stays visible, since those still need the user.
  if (finished === steps.length && !needsAttention) return null;
  // Partial credit for the step in flight, so the bar moves during a long step
  // instead of sitting still between whole-step jumps.
  const overall = Math.round(
    ((finished + (running ? Math.min(100, Math.max(0, running.progress_percent ?? 0)) / 100 : 0)) / steps.length) * 100,
  );

  return (
    <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
          Processing
        </h3>
        <span className="font-mono text-[11px] font-semibold text-neutral-400">{overall}%</span>
      </div>

      <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-800">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            hasFailure ? 'bg-rose-500' : overall >= 100 ? 'bg-emerald-400' : 'bg-amber-400'
          }`}
          style={{ width: `${overall}%` }}
        />
      </div>

      {/* Only steps that need the user are listed; progress is the percentage alone. */}
      {attentionSteps.map((step) => (
        <div
          key={step.step}
          className={`flex items-center justify-between p-2.5 rounded-lg border ${
            step.status === 'failed' ? 'bg-rose-500/5 border-rose-500/20' : 'bg-neutral-800 border-neutral-700'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {step.status === 'failed' ? (
              <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            ) : (
              <RotateCcw className="w-4 h-4 text-neutral-400 flex-shrink-0" />
            )}
            <div>
              <span className="text-xs font-semibold text-neutral-200 block">
                {STEP_LABELS[step.step] || step.step}
              </span>
              {step.message && (
                <span className="text-[10px] text-neutral-400 block truncate max-w-[340px]">{step.message}</span>
              )}
            </div>
          </div>
          {step.status === 'reverted' && onRevert && (
            <button
              onClick={() => onRevert(step.step)}
              className="px-2 py-1 rounded-md bg-neutral-800 hover:bg-neutral-700 text-[10px] font-semibold text-neutral-300 border border-neutral-700 transition-colors flex items-center gap-1"
            >
              <RotateCcw className="w-3 h-3" />
              Re-run
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
