'use client';

import { Play, Flame, ArrowRight, ChevronDown, Headphones } from 'lucide-react';
import { getCaptionStyle } from '@/lib/utils/captionStyles';

interface BeforeAfterShowcaseProps {
  previewCaptionPreset: 'hormozi' | 'mrbeast' | 'cyberpunk' | 'neon';
  setPreviewCaptionPreset: (preset: 'hormozi' | 'mrbeast' | 'cyberpunk' | 'neon') => void;
  onLaunchStudio: () => void;
}

export function BeforeAfterShowcase({
  previewCaptionPreset,
  setPreviewCaptionPreset,
  onLaunchStudio,
}: BeforeAfterShowcaseProps) {
  return (
    <div id="samples" className="scroll-mt-20 mt-14 max-w-5xl mx-auto">
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-4 sm:p-6 shadow-xl relative">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mb-4 pb-4 border-b border-neutral-800">
          <div className="flex items-center gap-2.5">
            <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif] flex items-center gap-1.5">
              <Flame className="w-4 h-4 text-amber-400" aria-hidden="true" />
              <span>Before &amp; After Example</span>
            </span>
          </div>

          <div role="group" aria-label="Caption preset" className="flex items-center gap-1.5 bg-neutral-950 p-1 rounded-xl border border-neutral-800 text-xs">
            <span aria-hidden="true" className="text-[10px] font-semibold text-neutral-300 px-2">Preset:</span>
            {(['hormozi', 'mrbeast', 'cyberpunk', 'neon'] as const).map((preset) => {
              const style = getCaptionStyle(preset);
              return (
                <button
                  key={preset}
                  onClick={() => setPreviewCaptionPreset(preset)}
                  aria-pressed={previewCaptionPreset === preset}
                  className={`px-2 py-1 rounded-lg text-[11px] font-bold transition-all ${
                    previewCaptionPreset === preset ? 'bg-neutral-800 text-amber-400 shadow' : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  {style.brandName}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid md:grid-cols-12 gap-6 items-center">
          <div className="md:col-span-5 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-neutral-300 font-semibold flex items-center gap-1.5">
                <span aria-hidden="true" className="w-2 h-2 rounded-full bg-neutral-600" />
                <span>Original 16:9 Long Video (Raw)</span>
              </span>
              <span className="text-[10px] text-neutral-400 font-mono">Podcast episode (48:20)</span>
            </div>

            <div className="relative aspect-video rounded-xl bg-black border border-neutral-800 overflow-hidden group">
                <img
                  src="https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&auto=format&fit=crop&q=80"
                  alt="Example source video: a podcast recorded in landscape 16:9"
                  className="w-full h-full object-cover opacity-75 grayscale-[30%]"
                />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-3">
                <div className="flex items-center justify-between text-[11px] text-neutral-300">
                  <span className="font-mono">Unedited Audio • 16:9</span>
                </div>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-neutral-950 border border-neutral-800/80 text-xs space-y-1">
              <div className="flex items-center justify-between text-[11px] text-neutral-300">
                <span>Strong moments found:</span>
                <span className="text-amber-400 font-bold font-mono">14 candidates</span>
              </div>
              <div aria-hidden="true" className="w-full bg-neutral-800 h-1.5 rounded-full overflow-hidden">
                <div className="bg-gradient-to-r from-amber-500 to-rose-500 h-full w-[85%]" />
              </div>
            </div>
          </div>

          <div className="md:col-span-2 flex flex-col items-center justify-center text-center py-2">
            <div aria-hidden="true" className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center shadow-lg animate-pulse mb-1">
              <ArrowRight className="w-5 h-5 hidden md:block" />
              <ChevronDown className="w-5 h-5 md:hidden" />
            </div>
            <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">AI Magic</span>
            <span className="text-[10px] text-neutral-400">Auto Crop & Denoise</span>
          </div>

          <div className="md:col-span-5 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                <span aria-hidden="true" className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                <span>AI Extracted 9:16 Short</span>
              </span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                SCORE: 98/100
              </span>
            </div>

            <div className="relative aspect-[9/16] max-h-[320px] mx-auto rounded-2xl bg-black border-2 border-amber-500/40 overflow-hidden shadow-2xl flex flex-col justify-between p-4">
              <img
                src="https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&auto=format&fit=crop&q=80"
                alt="The same podcast reframed as a vertical 9:16 clip with captions"
                className="absolute inset-0 w-full h-full object-cover scale-110"
              />

              <div className="relative z-10 flex items-center justify-between text-[10px] text-white/90 drop-shadow">
                <span className="bg-black/60 px-2 py-0.5 rounded backdrop-blur font-mono font-bold text-amber-400">
                  AUTO 9:16
                </span>
                <span className="bg-emerald-500/80 text-black font-extrabold px-1.5 py-0.5 rounded text-[9px]">
                  CAPTIONED
                </span>
              </div>

              <div className="relative z-10 text-center space-y-2 my-auto">
                <div className="inline-block px-3 py-1.5 rounded-xl bg-black/75 backdrop-blur-md border border-white/10 shadow-2xl">
                  <p className="text-sm font-black uppercase tracking-tight text-white font-['Syne',sans-serif]">
                    WHY{' '}
                    <span className="text-amber-300 underline decoration-amber-400 decoration-2">
                      99% OF CREATORS
                    </span>{' '}
                    FAIL!
                  </p>
                </div>
                <div className="text-[10px] font-bold text-amber-400 flex items-center justify-center gap-1 drop-shadow">
                  <span>Hook Detected at 0:14</span>
                </div>
              </div>

              <div className="relative z-10 p-2 rounded-xl bg-neutral-950/80 backdrop-blur border border-neutral-800 flex items-center justify-between text-[10px]">
                <div className="flex items-center gap-1.5 text-amber-300 font-bold">
                  <Headphones className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>Noise Reduced</span>
                </div>
                <div aria-hidden="true" className="flex items-end gap-0.5 h-3">
                  {[40, 80, 60, 100, 75, 45, 90].map((h, i) => (
                    <div key={i} className="w-1 bg-amber-400 rounded-full" style={{ height: `${h}%` }} />
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <button
                onClick={onLaunchStudio}
                className="w-full py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-amber-400 text-xs font-bold border border-neutral-700 flex items-center justify-center gap-1.5 transition-all active:scale-95"
              >
                <Play className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Try It on Your Video</span>
              </button>
            </div>
          </div>
        </div>
        <p className="mt-4 text-center text-[11px] text-neutral-400">
          Illustration of the workflow. The score is an example; real scores are estimates and do not predict views.
        </p>
      </div>
    </div>
  );
}
