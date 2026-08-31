"use client";

import React, { useState, useRef, useCallback } from 'react';
import {
  ShieldCheck,
  SlidersHorizontal,
  Mic2,
  Volume1,
  Waves,
  Play,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Radio,
  Headphones,
} from 'lucide-react';
import { AudioEnhancementConfig } from '@/lib/types';
import { audioApi } from '@/lib/api';

interface AudioEnhancerPanelProps {
  config: AudioEnhancementConfig;
  onConfigChange: (config: AudioEnhancementConfig) => void;
  onProcessed?: (result: { processedUrl?: string; processingTimeSeconds: number }) => void;
}

const DEFAULT_CONFIG: AudioEnhancementConfig = {
  aiDenoise: true,
  noiseSuppressionStrength: 90,
  deReverb: true,
  vocalClarityEq: true,
  humFilter: true,
};

export const AudioEnhancerPanel: React.FC<AudioEnhancerPanelProps> = ({
  config,
  onConfigChange,
  onProcessed,
}) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [lastResult, setLastResult] = useState<{ processedUrl?: string; processingTimeSeconds: number; error?: string } | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  const updateField = useCallback(<K extends keyof AudioEnhancementConfig>(
    key: K,
    value: AudioEnhancementConfig[K]
  ) => {
    const next = { ...config, [key]: value };
    onConfigChange(next);
  }, [config, onConfigChange]);

  const getZoneLabel = (value: number): string => {
    if (value <= 30) return 'Mild (Room Hum)';
    if (value <= 70) return 'Balanced Studio';
    return 'Max Vocal Isolation';
  };

  const handleBackendProcess = async () => {
    setIsProcessing(true);
    setLastResult(null);
    try {
      const result = await audioApi.process({
        audioUrl: '',
        config: {
          ai_denoise: config.aiDenoise,
          noise_suppression_strength: config.noiseSuppressionStrength,
          de_reverb: config.deReverb,
          vocal_clarity_eq: config.vocalClarityEq,
          hum_filter: config.humFilter,
        },
      });
      setLastResult({
        processedUrl: result.processedUrl,
        processingTimeSeconds: result.processingTimeSeconds,
        error: result.error,
      });
      onProcessed?.({ processedUrl: result.processedUrl, processingTimeSeconds: result.processingTimeSeconds });
    } catch (e) {
      setLastResult({ error: (e as Error).message, processingTimeSeconds: 0 });
    } finally {
      setIsProcessing(false);
    }
  };

  const handlePreview = async () => {
    if (isPreviewing) return;
    setIsPreviewing(true);
    try {
      const result = await audioApi.preview({
        frequencyHz: 440,
        durationSeconds: 2.5,
        config: {
          ai_denoise: config.aiDenoise,
          noise_suppression_strength: config.noiseSuppressionStrength,
          de_reverb: config.deReverb,
          vocal_clarity_eq: config.vocalClarityEq,
          hum_filter: config.humFilter,
        },
      });
      setLastResult({
        processedUrl: result.processedUrl,
        processingTimeSeconds: result.processingTimeSeconds,
        error: result.error,
      });
      onProcessed?.({ processedUrl: result.processedUrl, processingTimeSeconds: result.processingTimeSeconds });
    } catch (e) {
      setLastResult({ error: (e as Error).message, processingTimeSeconds: 0 });
    } finally {
      setIsPreviewing(false);
    }
  };

  const startLocalPreview = async () => {
    try {
      const ctx = new AudioContext({ sampleRate: 44100 });
      audioContextRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      const duration = 3;
      const sampleRate = ctx.sampleRate;
      const frameCount = sampleRate * duration;
      const buffer = ctx.createBuffer(1, frameCount, sampleRate);
      const data = buffer.getChannelData(0);

      const t = new Float32Array(frameCount);
      for (let i = 0; i < frameCount; i++) t[i] = i / sampleRate;

      const freq = 220;
      const tone = new Float32Array(frameCount);
      const noise = new Float32Array(frameCount);
      const hum = new Float32Array(frameCount);
      for (let i = 0; i < frameCount; i++) {
        tone[i] = 0.4 * Math.sin(2 * Math.PI * freq * t[i]);
        noise[i] = 0.06 * (Math.random() - 0.5);
        hum[i] = 0.1 * Math.sin(2 * Math.PI * 60 * t[i]) + 0.07 * Math.sin(2 * Math.PI * 120 * t[i]);
      }
      const audio = new Float32Array(frameCount);
      for (let i = 0; i < frameCount; i++) {
        audio[i] = tone[i] + noise[i] + hum[i];
      }
      const peakArr = Array.from(audio).map(Math.abs);
      const peak = Math.max(...peakArr);
      if (peak > 0) for (let i = 0; i < audio.length; i++) audio[i] /= peak;

      if (config.humFilter) {
        for (let i = 2; i < audio.length - 2; i++) {
          audio[i] = audio[i] - 0.5 * audio[i - 1] - 0.5 * audio[i + 1] + 0.25 * (audio[i - 2] + audio[i + 2]);
        }
      }

      if (config.vocalClarityEq) {
        const presence = new Float32Array(audio.length);
        for (let i = 0; i < audio.length; i++) {
          const env = Math.exp(-((t[i] * freq - 3000) ** 2) / (2 * 1500 ** 2));
          presence[i] = audio[i] * env * 0.3;
        }
        for (let i = 0; i < audio.length; i++) audio[i] += presence[i];
      }

      buffer.getChannelData(0).set(audio);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(analyser);
      analyser.connect(ctx.destination);
      source.start();
      source.onended = () => {
        ctx.close();
        audioContextRef.current = null;
        analyserRef.current = null;
      };
    } catch (e) {
      console.error('Local preview failed', e);
    }
  };

  const masterOn = config.aiDenoise;

  return (
    <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
            <Headphones className="w-4 h-4 text-amber-400" />
            <span>AI Background Noise Removal & Studio Voice</span>
          </h3>
          <p className="text-[11px] text-neutral-400">
            Isolates dialogue, eliminates room echo, microphone hiss, fan hum & background noise
          </p>
        </div>
        <span className={`text-[9px] font-mono px-2 py-0.5 rounded border font-bold ${
          masterOn
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            : 'bg-neutral-800 text-neutral-400 border-neutral-700'
        }`}>
          {masterOn ? 'DENOISE ACTIVE' : 'BYPASS'}
        </span>
      </div>

      {/* Master Toggle */}
      <div className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl border ${
            masterOn
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              : 'bg-neutral-900 border-neutral-800 text-neutral-500'
          }`}>
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-bold text-white block">AI Denoise</span>
            <span className="text-[10px] text-neutral-400">
              Master toggle for the entire noise-removal pipeline
            </span>
          </div>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={masterOn}
            onChange={(e) => updateField('aiDenoise', e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-9 h-5 bg-neutral-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500"></div>
        </label>
      </div>

      {/* Noise Suppression Strength */}
      <div className={`p-4 rounded-xl bg-neutral-950/80 border border-neutral-800 space-y-3 ${!masterOn ? 'opacity-50 pointer-events-none' : ''}`}>
        <div className="flex items-center justify-between text-xs">
          <span className="text-[11px] text-neutral-300 flex items-center gap-1.5">
            <SlidersHorizontal className="w-3.5 h-3.5 text-amber-400" />
            <span>Noise Suppression Strength</span>
          </span>
          <span className="font-mono text-amber-400 font-bold text-xs">
            {config.noiseSuppressionStrength}%
          </span>
        </div>

        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={config.noiseSuppressionStrength}
          onChange={(e) => updateField('noiseSuppressionStrength', Number(e.target.value))}
          className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
        />

        <div className="flex justify-between text-[9px] text-neutral-500 font-mono">
          <span className={config.noiseSuppressionStrength <= 30 ? 'text-amber-400' : ''}>Mild (Room Hum)</span>
          <span className={config.noiseSuppressionStrength > 30 && config.noiseSuppressionStrength <= 70 ? 'text-amber-400' : ''}>Balanced Studio</span>
          <span className={config.noiseSuppressionStrength > 70 ? 'text-amber-400' : ''}>Max Vocal Isolation</span>
        </div>
      </div>

      {/* Independent Toggles */}
      <div className={`grid grid-cols-1 sm:grid-cols-3 gap-2 ${!masterOn ? 'opacity-50 pointer-events-none' : ''}`}>
        <label className="flex items-center justify-between p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
          <div className="flex items-center gap-2">
            <Waves className="w-3.5 h-3.5 text-sky-400" />
            <div>
              <span className="text-[11px] font-bold text-white block">De-Reverb / Echo</span>
              <span className="text-[9px] text-neutral-400">Remove room reverb tail</span>
            </div>
          </div>
          <input
            type="checkbox"
            checked={config.deReverb}
            onChange={(e) => updateField('deReverb', e.target.checked)}
            className="w-3.5 h-3.5 rounded accent-amber-400"
          />
        </label>

        <label className="flex items-center justify-between p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
          <div className="flex items-center gap-2">
            <Mic2 className="w-3.5 h-3.5 text-emerald-400" />
            <div>
              <span className="text-[11px] font-bold text-white block">Vocal Clarity EQ</span>
              <span className="text-[9px] text-neutral-400">2-5kHz presence boost</span>
            </div>
          </div>
          <input
            type="checkbox"
            checked={config.vocalClarityEq}
            onChange={(e) => updateField('vocalClarityEq', e.target.checked)}
            className="w-3.5 h-3.5 rounded accent-amber-400"
          />
        </label>

        <label className="flex items-center justify-between p-2.5 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
          <div className="flex items-center gap-2">
            <Radio className="w-3.5 h-3.5 text-amber-400" />
            <div>
              <span className="text-[11px] font-bold text-white block">50/60Hz Hum Filter</span>
              <span className="text-[9px] text-neutral-400">Electrical hum notch</span>
            </div>
          </div>
          <input
            type="checkbox"
            checked={config.humFilter}
            onChange={(e) => updateField('humFilter', e.target.checked)}
            className="w-3.5 h-3.5 rounded accent-amber-400"
          />
        </label>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleBackendProcess}
          disabled={isProcessing}
          className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-neutral-950 font-bold text-xs shadow-lg shadow-rose-500/25 active:scale-95 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
        >
          {isProcessing ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Processing...
            </>
          ) : (
            <>Process Audio</>
          )}
        </button>
        <button
          onClick={startLocalPreview}
          disabled={isPreviewing}
          className="px-4 py-2.5 rounded-xl bg-neutral-800 border border-neutral-700 text-neutral-200 font-bold text-xs hover:bg-neutral-700 active:scale-95 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
        >
          {isPreviewing ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5" />
          )}
          Preview
        </button>
      </div>

      {/* Result */}
      {lastResult && (
        <div className={`p-3 rounded-xl border flex items-start gap-2 text-[11px] ${
          lastResult.error
            ? 'bg-red-500/10 border-red-500/20 text-red-400'
            : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
        }`}>
          {lastResult.error ? (
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          )}
          <div>
            {lastResult.error ? (
              <span className="font-semibold">Processing failed: {lastResult.error}</span>
            ) : (
              <>
                <span className="font-semibold">Processing complete in {lastResult.processingTimeSeconds}s</span>
                {lastResult.processedUrl && (
                  <span className="block text-neutral-400 mt-0.5">Output ready: {lastResult.processedUrl}</span>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};