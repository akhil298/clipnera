import { useState, useEffect, useRef, RefObject } from 'react';
import { DownloadProgress } from '@/lib/types';

export interface UseDownloadProgressResult {
  progress: DownloadProgress;
  isPolling: boolean;
  start: (projectId: string) => void;
  stop: () => void;
  reset: () => void;
}

export function useDownloadProgress(): UseDownloadProgressResult {
  const [progress, setProgress] = useState<DownloadProgress>({
    status: 'idle',
    percent: 0,
    total: null,
    speed: null,
    eta: null,
  });
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const pollProgress = async (projectId: string) => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1/clips/progress/${projectId}`, {
        headers: {
          'Content-Type': 'application/json',
          ...(typeof window !== 'undefined' && localStorage.getItem('token')
            ? { Authorization: `Bearer ${localStorage.getItem('token')}` }
            : {}),
        },
      });

      if (!res.ok) {
        throw new Error(`Failed to fetch progress: ${res.status}`);
      }

      const data = (await res.json()) as DownloadProgress;
      setProgress(data);

      if (data.status === 'done' || data.status === 'error') {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        setIsPolling(false);
      }
    } catch (err) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsPolling(false);
      setProgress((prev) => ({ ...prev, status: 'error', message: (err as Error).message }));
    }
  };

  const start = (projectId: string) => {
    setProgress({
      status: 'pending',
      percent: 0,
      total: null,
      speed: null,
      eta: null,
    });
    setIsPolling(true);

    const tick = () => {
      pollProgress(projectId);
    };

    tick();
    intervalRef.current = setInterval(tick, 500);
  };

  const stop = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  };

  const reset = () => {
    stop();
    setProgress({
      status: 'idle',
      percent: 0,
      total: null,
      speed: null,
      eta: null,
    });
  };

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return { progress, isPolling, start, stop, reset };
}
