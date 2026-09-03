'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

interface FaqSectionProps {
  faqs: Array<{ q: string; a: string }>;
}

export function FaqSection({ faqs }: FaqSectionProps) {
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  return (
    <section className="py-16 bg-neutral-950/80 border-t border-neutral-800/80">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="text-center space-y-2">
          <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">
            Got Questions?
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white font-['Syne',sans-serif]">
            Frequently Asked Questions
          </h2>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="rounded-xl bg-neutral-900/90 border border-neutral-800 overflow-hidden transition-colors"
            >
              <button
                onClick={() => setOpenFaqIndex(openFaqIndex === index ? null : index)}
                className="w-full p-4 text-left flex items-center justify-between text-xs sm:text-sm font-bold text-white hover:text-amber-300 transition-colors"
              >
                <span>{faq.q}</span>
                <ChevronDown
                  className={`w-4 h-4 text-neutral-400 transition-transform ${
                    openFaqIndex === index ? 'rotate-180 text-amber-400' : ''
                  }`}
                />
              </button>
              {openFaqIndex === index && (
                <div className="px-4 pb-4 text-xs text-neutral-300 leading-relaxed border-t border-neutral-800/50 pt-3">
                  {faq.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
