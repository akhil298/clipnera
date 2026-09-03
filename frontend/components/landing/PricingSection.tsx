'use client';

import { Check } from 'lucide-react';

interface PricingSectionProps {
  onLaunchStudio: () => void;
}

export function PricingSection({ onLaunchStudio }: PricingSectionProps) {
  const plans = [
    {
      name: 'Starter Free',
      description: 'Perfect for testing and getting started',
      price: '$0',
      period: '/month',
      features: [
        '60 AI Processing Minutes / mo',
        'Auto 9:16 Reframe & Face Tracking',
        'Hormozi & MrBeast Caption Styles',
        'Studio Noise Cancellation',
      ],
      buttonText: 'Get Started Free',
      buttonClass: 'bg-neutral-800 hover:bg-neutral-700 text-white',
      highlighted: false,
    },
    {
      name: 'Creator Pro',
      description: 'For active YouTubers & podcast creators',
      price: '$29',
      period: '/month',
      features: [
        '300 AI Processing Minutes / mo',
        'Prompt-to-Shorts Story AI Generator',
        'Full Custom Brand Kits & Watermarks',
        'Multi-Platform Auto Scheduler',
        '4K 60fps Ultra HD Export',
      ],
      buttonText: 'Upgrade to Pro',
      buttonClass: 'bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-md shadow-amber-500/15',
      highlighted: true,
    },
    {
      name: 'Agency & Team',
      description: 'Multi-client management & shared workspaces',
      price: '$79',
      period: '/month',
      features: [
        '1,200 AI Processing Minutes / mo',
        'Unlimited Client Workspaces',
        'Team Collaboration & Shared Brand Kits',
        'Priority Rendering Pipeline',
      ],
      buttonText: 'Choose Agency',
      buttonClass: 'bg-neutral-800 hover:bg-neutral-700 text-white',
      highlighted: false,
    },
  ];

  return (
    <section id="pricing" className="py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
            Transparent Pricing
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-['Syne',sans-serif]">
            Simple plans for creators of all sizes
          </h2>
          <p className="text-xs text-neutral-400">
            Start with free monthly credits. Upgrade whenever you need more video processing power.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`p-6 rounded-2xl space-y-6 flex flex-col justify-between relative ${
                plan.highlighted
                  ? 'bg-gradient-to-b from-neutral-900 via-neutral-900 to-neutral-950 border-2 border-amber-500/60 shadow-xl shadow-amber-500/10'
                  : 'bg-neutral-900/90 border border-neutral-800'
              }`}
            >
              {plan.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-amber-500 text-[10px] font-extrabold text-neutral-950 uppercase tracking-wider">
                  Most Popular
                </div>
              )}
              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">{plan.name}</h3>
                  <p className="text-xs text-neutral-400 mt-1">{plan.description}</p>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold text-white font-mono">{plan.price}</span>
                  <span className="text-xs text-neutral-400">{plan.period}</span>
                </div>
                <ul className="space-y-2.5 text-xs text-neutral-300">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <button
                onClick={onLaunchStudio}
                className={`w-full py-2.5 rounded-xl text-xs font-bold transition-all active:scale-95 ${plan.buttonClass}`}
              >
                {plan.buttonText}
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
