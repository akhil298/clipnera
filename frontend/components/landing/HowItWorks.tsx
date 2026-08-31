'use client';

export function HowItWorks() {
  const steps = [
    {
      num: '01',
      title: 'Ingest URL, Upload or Prompt',
      description: 'Paste any YouTube video link, drag in raw podcast files, or provide a text story prompt. Our ingestion engine parses audio streams instantly.',
    },
    {
      num: '02',
      title: 'AI Denoise & Clip Extraction',
      description: 'Gemini 3.7 isolates highest-virality segments, eliminates background room hum, centers speakers at 9:16, and generates kinetic subtitles.',
    },
    {
      num: '03',
      title: 'Refine in Studio & Auto-Post',
      description: 'Fine-tune captions, drop sound effects, and schedule directly to TikTok, YouTube Shorts, and Instagram Reels with 1 click.',
    },
  ];

  return (
    <section id="how-it-works" className="py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
            Simple 3-Step Flow
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-['Syne',sans-serif]">
            From raw footage to 10 viral shorts in under a minute
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-8 relative">
          {steps.map((step) => (
            <div key={step.num} className="p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4">
              <div className={`text-4xl font-extrabold font-['Syne',sans-serif] ${
                step.num === '01' ? 'text-neutral-700' : step.num === '02' ? 'text-amber-500/50' : 'text-emerald-500/50'
              }`}>
                {step.num}
              </div>
              <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">{step.title}</h3>
              <p className="text-xs text-neutral-400 leading-relaxed">{step.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
