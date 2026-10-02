"use client";
import React from 'react';
import { CONTENT_FORMAT_LABELS, ContentFormat } from '@/lib/formats';

interface FormatBadgeProps {
  format: ContentFormat | null | undefined;
  className?: string;
}

/** Read-only label of the short-form format the AI cut a clip as; nothing for older clips. */
export function FormatBadge({ format, className = '' }: FormatBadgeProps) {
  if (!format) return null;
  return (
    <span
      title="Format chosen by AI for this clip"
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${className}`}
    >
      {CONTENT_FORMAT_LABELS[format]}
    </span>
  );
}
