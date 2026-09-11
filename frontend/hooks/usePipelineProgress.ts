import { useState, useEffect, useRef, useCallback } from 'react';
import { PipelineStep, PipelineProgressEvent } from '@/lib/types';
import { pipelineApi } from '@/lib/api';

export interface UsePipelineProgressResult {
  steps: PipelineStep[];
  progress: PipelineProgressEvent;
  currentStep: string | null;
  creditsDeducted: number;
  isProcessing: boolean;
  error: string | null;
  refetchStatus: () => void;
}

export function usePipelineProgress(
  projectId: string | null,
  selectedSteps: string[] | null,
  initialCreditsDeducted: number = 0,
): UsePipelineProgressResult {
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [progress, setProgress] = useState<PipelineProgressEvent>({
    message: '',
    percent: 0,
    status: 'idle',
  });
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [creditsDeducted, setCreditsDeducted] = useState<number>(initialCreditsDeducted);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sseUnsubRef = useRef<(() => void) | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const initSteps = useCallback((stepNames: string[]) => {
    setSteps(
      stepNames.map((s) => ({
        step: s,
        status: 'pending',
        progress_percent: 0,
        message: null,
        artifact_path: null,
        started_at: null,
        finished_at: null,
      }))
    );
  }, []);

  const updateStep = useCallback((stepName: string, updates: Partial<PipelineStep>) => {
    setSteps((prev) =>
      prev.map((s) => (s.step === stepName ? { ...s, ...updates } : s))
    );
  }, []);

  const refetchStatus = useCallback(async () => {
    if (!projectId) return;
    try {
      const status = await pipelineApi.getStatus(projectId);
      setSteps(status.steps || []);
      if (status.is_completed || status.error) {
        setIsProcessing(false);
        if (status.error) setError(status.error);
      } else if (status.steps && status.steps.length > 0) {
        setIsProcessing(true);
      }
    } catch {
      // Silent fail - SSE is the primary channel
    }
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !selectedSteps || selectedSteps.length === 0) {
      return;
    }

    const selectedStepsKey = selectedSteps.join(',');

    initSteps(selectedSteps);
    setCreditsDeducted(initialCreditsDeducted);
    setIsProcessing(true);
    setError(null);
    setProgress({
      message: 'Pipeline started...',
      percent: 0,
      status: 'running',
    });

    const unsubSse = pipelineApi.subscribeProgress(
      projectId,
      (data: PipelineProgressEvent) => {
        setProgress(data);
        setCurrentStep(data.current_step ?? null);

        if (data.current_step && data.step_status) {
          updateStep(data.current_step, {
            status: data.step_status,
            progress_percent: data.percent,
            message: data.message,
          });
        }

        if (data.status === 'completed') {
          setIsProcessing(false);
          if (data.current_step) {
            updateStep(data.current_step, {
              status: 'completed',
              progress_percent: 100,
            });
          }
        } else if (data.status === 'error') {
          setIsProcessing(false);
          setError(data.message || 'Pipeline failed');
        } else {
          setIsProcessing(true);
        }
      },
      (err: Error) => {
        console.error('Pipeline progress stream error:', err);
      }
    );

    sseUnsubRef.current = unsubSse;

    const pollTimer = setInterval(() => {
      refetchStatus();
    }, 3000);
    pollIntervalRef.current = pollTimer;

    refetchStatus();

    return () => {
      unsubSse();
      sseUnsubRef.current = null;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [projectId, selectedSteps, initialCreditsDeducted, refetchStatus, updateStep, initSteps]);

  useEffect(() => {
    setCreditsDeducted(initialCreditsDeducted);
  }, [initialCreditsDeducted]);

  return {
    steps,
    progress,
    currentStep,
    creditsDeducted,
    isProcessing,
    error,
    refetchStatus,
  };
}
