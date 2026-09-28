import type { ReactNode } from 'react';

interface SectionIntroProps {
  eyebrow: string;
  title: ReactNode;
  children?: ReactNode;
  /** Put the paragraph beside the title on wide screens instead of below it. */
  inline?: boolean;
}

/** The mono eyebrow, display heading and lead paragraph every landing section opens with. */
export function SectionIntro({ eyebrow, title, children, inline = false }: SectionIntroProps) {
  return (
    <div className="space-y-4">
      <p className="font-jetbrains text-xs font-medium uppercase tracking-[0.14em] text-amber-400">{eyebrow}</p>
      <div className={inline ? 'flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between lg:gap-12' : 'space-y-5'}>
        <h2 className="font-syne text-[28px] font-extrabold leading-none tracking-[-0.03em] text-white sm:text-5xl lg:text-[54px]">
          {title}
        </h2>
        {children && <p className="max-w-[440px] text-base leading-relaxed text-neutral-300">{children}</p>}
      </div>
    </div>
  );
}
