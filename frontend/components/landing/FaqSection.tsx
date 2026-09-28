'use client';

import { useState } from 'react';
import { Minus, Plus } from 'lucide-react';

interface FaqSectionProps {
  faqs: Array<{ q: string; a: string }>;
}

export function FaqSection({ faqs }: FaqSectionProps) {
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="scroll-mt-20 border-t border-neutral-900 py-20">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-10 px-4 sm:px-8 lg:flex-row lg:gap-24 xl:px-16">
        <div className="space-y-3.5 lg:w-[420px] lg:flex-shrink-0 lg:pt-5">
          <p className="font-jetbrains text-xs font-medium uppercase tracking-[0.14em] text-amber-400">FAQ</p>
          <h2 className="font-syne text-[28px] font-extrabold leading-none tracking-[-0.03em] text-white sm:text-[44px]">
            Straight answers.
          </h2>
        </div>

        <div className="flex-1">
          {faqs.map((faq, index) => {
            const open = openFaqIndex === index;
            return (
              <div key={faq.q} className="border-b border-neutral-800 py-5">
                <button
                  onClick={() => setOpenFaqIndex(open ? null : index)}
                  aria-expanded={open}
                  aria-controls={`faq-answer-${index}`}
                  className="flex w-full items-center justify-between gap-6 text-left text-[17px] font-bold text-white transition-colors hover:text-amber-300"
                >
                  <span>{faq.q}</span>
                  {open ? (
                    <Minus className="h-4 w-4 flex-shrink-0 text-amber-400" aria-hidden="true" />
                  ) : (
                    <Plus className="h-4 w-4 flex-shrink-0 text-neutral-500" aria-hidden="true" />
                  )}
                </button>
                {open && (
                  <p id={`faq-answer-${index}`} className="mt-3 max-w-3xl text-sm leading-relaxed text-neutral-400">
                    {faq.a}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
