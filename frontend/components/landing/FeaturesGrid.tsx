'use client';

import { TrendingUp, Headphones, Wand2, Sliders, Film, Share2 } from 'lucide-react';

export function FeaturesGrid() {
  const features: Array<{
    id?: string;
    icon: typeof TrendingUp;
    color: string;
    title: string;
    description: string;
    badge: string;
    badgeColor: string;
  }> = [
    {
      icon: TrendingUp,
      color: 'amber',
      title: 'AI Moment Detection',
      description: 'AI reads your transcript and scores each moment for its hook, emotion and payoff, then cuts the strongest ones into clips with an estimated virality score.',
      badge: 'Virality score out of 100 on every clip',
      badgeColor: 'text-amber-300',
    },
    {
      id: 'denoise',
      icon: Headphones,
      color: 'amber',
      title: 'Background Noise Reduction',
      description: 'Reduces background noise, electrical hum and room echo, and evens out voice tone in one click.',
      badge: 'Noise reduction • Hum filter • De-reverb',
      badgeColor: 'text-emerald-400',
    },
    {
      id: 'story-generator',
      icon: Wand2,
      color: 'purple',
      title: 'Prompt-to-Shorts Story AI',
      description: 'Type a story idea or script. Clipnera plans the scenes, adds a voiceover and captions, and renders a 9:16 short.',
      badge: 'Text Prompt ➔ 9:16 Video Short',
      badgeColor: 'text-purple-300',
    },
    {
      icon: Sliders,
      color: 'rose',
      title: 'Kinetic Subtitle Presets',
      description: 'Animated caption presets with word-by-word highlights and automatic emojis that match what is being said.',
      badge: 'Word-by-word highlights • Auto emojis',
      badgeColor: 'text-amber-300',
    },
    {
      icon: Film,
      color: 'sky',
      title: 'Smart B-Roll & Sound Effects',
      description: 'Adds stock footage cutaways that match what the speaker is talking about, and transition sound effects such as whooshes and glitches.',
      badge: 'Stock B-roll cutaways • Transition SFX',
      badgeColor: 'text-sky-300',
    },
    {
      icon: Share2,
      color: 'emerald',
      title: 'Multi-Platform Publishing',
      description: 'Publish clips to TikTok, Instagram Reels and YouTube Shorts from one place. Scheduling and posting to X are included in Pro.',
      badge: 'TikTok • Reels • Shorts • X',
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
            id={feature.id}
            className={`scroll-mt-20 p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 ${colors.hoverBorder} transition-all space-y-4 group`}
          >
            <div className={`w-12 h-12 rounded-xl ${colors.bg} ${colors.border} ${colors.text} flex items-center justify-center group-hover:scale-110 transition-transform`}>
              <Icon className="w-6 h-6" aria-hidden="true" />
            </div>
            <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">{feature.title}</h3>
            <p className="text-xs text-neutral-300 leading-relaxed">{feature.description}</p>
            <div className={`p-3 rounded-xl bg-neutral-950 border border-neutral-800/80 font-mono text-[11px] ${feature.badgeColor}`}>
              {feature.badge}
            </div>
          </div>
        );
      })}
    </div>
  );
}
