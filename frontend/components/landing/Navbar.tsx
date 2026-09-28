'use client';

import { BrandMark } from './BrandMark';

const LINKS = [
  { href: '#clip-wall', label: 'Clip wall' },
  { href: '#how-it-works', label: 'How it works' },
  { href: '#captions', label: 'Captions' },
  { href: '#pricing', label: 'Pricing' },
];

export function Navbar({ onOpenAuthModal, onLaunchStudio }: { onOpenAuthModal: () => void; onLaunchStudio: () => void }) {
  return (
    <header className="sticky top-0 z-50 border-b border-neutral-900 bg-neutral-950/90 backdrop-blur-md">
      <div className="mx-auto flex h-[76px] max-w-[1440px] items-center justify-between px-4 sm:px-8 xl:px-16">
        <button
          type="button"
          aria-label="Clipnera, back to top"
          className="rounded-xl"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        >
          <BrandMark />
        </button>

        <nav aria-label="Main" className="hidden items-center gap-9 text-sm font-medium text-neutral-300 md:flex">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href} className="transition-colors hover:text-white">
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-5">
          <button onClick={onOpenAuthModal} className="hidden text-sm font-semibold text-neutral-200 transition-colors hover:text-white sm:inline">
            Sign in
          </button>
          <button
            onClick={onLaunchStudio}
            className="flex h-11 items-center rounded-xl bg-amber-500 px-5 text-sm font-bold text-neutral-950 transition-colors hover:bg-amber-400 active:scale-[0.98]"
          >
            Start free
          </button>
        </div>
      </div>
    </header>
  );
}
