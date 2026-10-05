'use client';

import { UploadCloud } from 'lucide-react';
import { type DragEvent, type ReactNode, useId, useRef, useState } from 'react';

import { cx, focusWithinRing } from '@/lib/design/styles';

export interface FileDropzoneProps {
  /** "Drop a video, or choose a file". */
  title: ReactNode;
  /** Formats and limits: "MP4, MOV or WebM, up to 4 GB". */
  hint?: ReactNode;
  /** Same syntax as the input's `accept`: `video/*,.mov`. Files that do not match are rejected. */
  accept?: string;
  multiple?: boolean;
  /** Largest file in bytes. */
  maxSize?: number;
  onFiles: (files: File[]) => void;
  /** Files that were turned away, with the reason in words. */
  onReject?: (rejected: ReadonlyArray<{ file: File; reason: string }>) => void;
  disabled?: boolean;
  /** Says why it is disabled (plan limit, storage full). Shown in place of the hint. */
  disabledReason?: ReactNode;
  /** Error from the last attempt; shown under the title in rose. */
  error?: ReactNode;
  icon?: ReactNode;
  compact?: boolean;
  className?: string;
}

function matchesAccept(file: File, accept?: string): boolean {
  if (!accept) return true;
  const name = file.name.toLowerCase();
  return accept.split(',').some((raw) => {
    const rule = raw.trim().toLowerCase();
    if (rule.startsWith('.')) return name.endsWith(rule);
    if (rule.endsWith('/*')) return file.type.startsWith(rule.slice(0, -1));
    return file.type === rule;
  });
}

const formatBytes = (bytes: number) =>
  bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${Math.round(bytes / 1024 ** 2)} MB`;

/**
 * Drop files or choose them. A real file input sits inside the label, so a
 * click, Enter or Space opens the picker, and drag and drop is a shortcut,
 * never the only way (WCAG 2.5.7).
 */
export function FileDropzone({
  title,
  hint,
  accept,
  multiple = false,
  maxSize,
  onFiles,
  onReject,
  disabled = false,
  disabledReason,
  error,
  icon = <UploadCloud />,
  compact = false,
  className,
}: FileDropzoneProps) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const depth = useRef(0);

  const take = (list: FileList | null) => {
    if (!list || disabled) return;
    const files = Array.from(list).slice(0, multiple ? undefined : 1);
    const accepted: File[] = [];
    const rejected: Array<{ file: File; reason: string }> = [];
    for (const file of files) {
      if (!matchesAccept(file, accept)) rejected.push({ file, reason: `${file.name} is not a supported file type.` });
      else if (maxSize !== undefined && file.size > maxSize) rejected.push({ file, reason: `${file.name} is larger than ${formatBytes(maxSize)}.` });
      else accepted.push(file);
    }
    if (accepted.length > 0) onFiles(accepted);
    if (rejected.length > 0) onReject?.(rejected);
    if (inputRef.current) inputRef.current.value = '';
  };

  const onDragEnter = (event: DragEvent) => {
    event.preventDefault();
    depth.current += 1;
    if (!disabled) setDragging(true);
  };
  const onDragLeave = () => {
    depth.current -= 1;
    if (depth.current <= 0) {
      depth.current = 0;
      setDragging(false);
    }
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    depth.current = 0;
    setDragging(false);
    take(event.dataTransfer.files);
  };

  const describe = [error ? `${id}-error` : '', `${id}-hint`].filter(Boolean).join(' ');

  return (
    <label
      htmlFor={id}
      onDragEnter={onDragEnter}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={cx(
        'flex flex-col items-center justify-center gap-2 rounded-cn-xl border border-dashed text-center transition-colors duration-cn-fast',
        compact ? 'px-4 py-6' : 'px-6 py-12',
        disabled
          ? 'cursor-not-allowed border-cn-border opacity-60'
          : dragging
            ? 'cursor-copy border-cn-accent-border bg-cn-accent-subtle'
            : error
              ? 'cursor-pointer border-cn-danger-text hover:bg-cn-surface-hover'
              : 'cursor-pointer border-cn-control-border hover:border-cn-fg-muted hover:bg-cn-surface-hover active:bg-cn-surface-active',
        focusWithinRing,
        className,
      )}
    >
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        aria-describedby={describe}
        aria-invalid={error ? true : undefined}
        onChange={(event) => take(event.target.files)}
        className="sr-only"
      />
      <span
        aria-hidden
        className={cx(
          'inline-flex items-center justify-center rounded-cn-lg border border-cn-border bg-cn-surface [&_svg]:size-5',
          compact ? 'size-10' : 'size-12',
          dragging ? 'text-cn-accent-text' : 'text-cn-fg-secondary',
        )}
      >
        {icon}
      </span>
      <span className="text-cn-body font-semibold text-cn-fg">{dragging ? 'Drop to add' : title}</span>
      {error && (
        <span id={`${id}-error`} className="text-cn-label font-medium text-cn-danger-text">
          {error}
        </span>
      )}
      <span id={`${id}-hint`} className="max-w-md text-cn-label text-cn-fg-muted">
        {disabled && disabledReason ? disabledReason : hint}
      </span>
    </label>
  );
}
