'use client';

import { getAllCaptionStyles } from '@/lib/utils/captionStyles';

export function CaptionTypographyShowcase() {
  const styles = getAllCaptionStyles();

  return (
    <section id="captions" className="py-16 border-t border-neutral-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        <div className="text-center max-w-3xl mx-auto space-y-3">
          <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
            Caption Typography & Animation
          </span>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-white font-['Syne',sans-serif]">
            7 viral caption presets. One click.
          </h2>
          <p className="text-xs sm:text-sm text-neutral-400">
            Choose from proven viral typography styles. Each preset is tuned for maximum watchtime, retention, and scroll-stopping power.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {styles.map((style) => (
            <div
              key={style.id}
              className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 hover:border-amber-500/40 transition-all space-y-3 group"
            >
              <div className="space-y-1">
                <h3 className="text-sm font-black text-white font-['Syne',sans-serif] tracking-tight group-hover:text-amber-300 transition-colors">
                  {style.brandName}
                </h3>
                <p className="text-[11px] text-neutral-500 font-medium">
                  {style.name}
                </p>
              </div>

              <p className="text-[11px] text-neutral-400 leading-relaxed">
                {style.description}
              </p>

              <div className="flex items-center justify-between pt-2 border-t border-neutral-800/80">
                <span className="text-[10px] px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 font-bold">
                  {style.badge}
                </span>
                <span className="text-[10px] text-neutral-500 font-mono capitalize">
                  {style.config.animation}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
