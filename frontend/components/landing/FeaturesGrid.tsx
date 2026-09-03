'use client';

import { TrendingUp, Headphones, Wand2, Sliders, Film, Share2 } from 'lucide-react';

export function FeaturesGrid() {
  const features = [
    {
      icon: TrendingUp,
      color: 'amber',
      title: 'AI Virality Spike Detection',
      description: 'Gemini 3.7 parses speech cadences to score the emotional peak of every sentence. It pinpoints the exact 3-second hook that stops users from scrolling.',
      badge: 'Hook Score: 99% • Attention Index: 9.8/10',
      badgeColor: 'text-amber-300',
    },
    {
      icon: Headphones,
      color: 'amber',
      title: 'AI Background Noise Removal',
      description: 'Neural voice isolation strips out room echo, air conditioner hum, and mic noise in one click, outputting studio-isolated vocal clarity.',
      badge: 'Studio Denoise: ACTIVE',
      badgeColor: 'text-emerald-400',
      badgeExtra: '-32dB Noise Floor',
    },
    {
      icon: Wand2,
      color: 'purple',
      title: 'Prompt-to-Shorts Story AI',
      description: 'Type any story concept or script outline. Clipnera synthesizes 9:16 scenes, voiceover narration, cinematic art posters, and kinetic captions instantly.',
      badge: 'Text Prompt ➔ Full 9:16 Video Short',
      badgeColor: 'text-purple-300',
    },
    {
      icon: Sliders,
      color: 'rose',
      title: 'Kinetic Subtitle Presets',
      description: 'Hormozi, MrBeast, Cyberpunk, and Neon caption animations with dynamic word-by-word karaoke highlights and auto-generated contextual emojis.',
      badge: 'HORMOZI • MRBEAST • NEON • CYBERPUNK',
      badgeColor: 'text-amber-300',
    },
    {
      icon: Film,
      color: 'sky',
      title: 'Smart B-Roll & SFX Ingestion',
      description: 'Automatically overlays relevant contextual footage and triggers cinematic sound effects (whooshes, sub drops, glitches) on climax beats.',
      badge: '+45% Visual Novelty Factor',
      badgeColor: 'text-sky-300',
    },
    {
      icon: Share2,
      color: 'emerald',
      title: 'Multi-Platform Auto Scheduler',
      description: '1-click auto-schedule to TikTok, Instagram Reels, YouTube Shorts, and X at the optimal algorithmic peak hours calculated for your niche.',
      badge: 'TikTok • Reels • Shorts • X Auto-Post',
      badgeColor: 'text-emerald-400',
    },
  ];

  const colorMap: Record<string, { bg: string; border: string; hoverBorder: string; text: string }> = {
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', hoverBorder: 'hover:border-amber-500/40', text: 'text-amber-400' },
    purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/20', hoverBorder: 'hover:border-purple-500/40', text: 'text-purple-400' },
    rose: { bg: 'bg-rose-500/10', border: 'border-rose-500/20', hoverBorder: 'hover:border-rose-500/40', text: 'text-rose-400' },
    sky: { bg: 'bg-sky-500/10', border: 'border-sky-500/20', hoverBorder: 'hover:border-sky-500/40', text: 'text-sky-400' },
    emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', hoverBorder: 'hover:border-emerald-500/40', text: 'text-emerald-400' },
  };

  return (
    <div className="grid md:grid-cols-3 gap-6">
      {features.map((feature, index) => {
        const colors = colorMap[feature.color];
        const Icon = feature.icon;
        return (
          <div
            key={index}
            className={`p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 ${colors.hoverBorder} transition-all space-y-4 group`}
          >
            <div className={`w-12 h-12 rounded-xl ${colors.bg} ${colors.border} ${colors.text} flex items-center justify-center group-hover:scale-110 transition-transform`}>
              <Icon className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">{feature.title}</h3>
            <p className="text-xs text-neutral-400 leading-relaxed">{feature.description}</p>
            <div className={`p-3 rounded-xl bg-neutral-950 border border-neutral-800/80 font-mono text-[11px] ${feature.badgeColor} ${feature.badgeExtra ? 'flex items-center justify-between' : ''}`}>
              <span>{feature.badge}</span>
              {feature.badgeExtra && <span>{feature.badgeExtra}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
