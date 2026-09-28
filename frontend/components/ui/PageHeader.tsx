import React from 'react';
import { ArrowLeft } from 'lucide-react';

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Buttons on the right; the primary one goes last. */
  actions?: React.ReactNode;
  /** Small row above the title, e.g. status pills. */
  eyebrow?: React.ReactNode;
  back?: { label: string; onClick: () => void };
}

/**
 * The top of every signed-in page: a one-line title, a short description and
 * the page's actions. Replaces the landing-page style heroes so the work sits
 * above the fold.
 */
export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, actions, eyebrow, back }) => (
  <div className="space-y-3">
    {back && (
      <button
        type="button"
        onClick={back.onClick}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-neutral-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        {back.label}
      </button>
    )}
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 space-y-1.5">
        {eyebrow && <div className="flex flex-wrap items-center gap-2">{eyebrow}</div>}
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white text-balance">{title}</h1>
        {description && <p className="text-sm text-neutral-400 max-w-2xl">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  </div>
);
