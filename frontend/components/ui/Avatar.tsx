'use client';

import { ChevronsUpDown } from 'lucide-react';
import { useState } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { Menu, type MenuEntry } from './Menu';

const SIZE = { 24: 'size-6 text-cn-caption', 32: 'size-8 text-cn-caption', 40: 'size-10 text-cn-label' } as const;
export type AvatarSize = keyof typeof SIZE;

export type AvatarStatus = 'online' | 'busy' | 'away';
const STATUS: Record<AvatarStatus, { dot: string; word: string }> = {
  online: { dot: 'bg-cn-success', word: 'online' },
  busy: { dot: 'bg-cn-danger', word: 'busy' },
  away: { dot: 'bg-cn-fg-muted', word: 'away' },
};

export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : (parts[0] ?? '?').slice(0, 2);
  return letters.toUpperCase();
}

export interface AvatarProps {
  /** Person or workspace name: the initials fallback and, with `labelled`, the accessible name. */
  name: string;
  src?: string;
  size?: AvatarSize;
  /** Workspaces are rounded squares so they never read as a person. */
  shape?: 'person' | 'workspace';
  /** Set when the avatar is the only place the name appears; otherwise it is decorative. */
  labelled?: boolean;
  status?: AvatarStatus;
  className?: string;
}

/**
 * A person or workspace picture, falling back to initials on `surface-active`
 * when there is no image or it fails to load (02 §3.23).
 */
export function Avatar({ name, src, size = 32, shape = 'person', labelled = false, status, className }: AvatarProps) {
  const [failed, setFailed] = useState(false);
  const rounded = shape === 'workspace' ? 'rounded-cn-sm' : 'rounded-cn-full';
  const showImage = src && !failed;
  const label = status ? `${name}, ${STATUS[status].word}` : name;
  return (
    <span
      role={labelled ? 'img' : undefined}
      aria-label={labelled ? label : undefined}
      aria-hidden={labelled ? undefined : true}
      className={cx('relative inline-flex shrink-0', SIZE[size], className)}
    >
      {showImage ? (
        <img src={src} alt="" onError={() => setFailed(true)} className={cx('size-full object-cover', rounded)} />
      ) : (
        <span className={cx('inline-flex size-full items-center justify-center bg-cn-surface-active font-semibold text-cn-fg-secondary', rounded)}>
          {initialsOf(name)}
        </span>
      )}
      {status && (
        <span className={cx('absolute -bottom-0.5 -right-0.5 size-2.5 rounded-cn-full ring-2 ring-cn-bg', STATUS[status].dot)} />
      )}
    </span>
  );
}

export interface AvatarMenuProps {
  name: string;
  /** Second line: email, or "Pro · Acme Studio". */
  detail?: string;
  src?: string;
  items: ReadonlyArray<MenuEntry>;
  /** Hide the name and detail (collapsed sidebar rail, top bar on phones). */
  compact?: boolean;
  side?: 'top' | 'bottom';
  align?: 'start' | 'end';
  className?: string;
}

/** The account button: avatar, name and detail, opening a Menu (workspaces, settings, sign out). */
export function AvatarMenu({ name, detail, src, items, compact = false, side = 'bottom', align = 'start', className }: AvatarMenuProps) {
  return (
    <Menu
      side={side}
      align={align}
      items={items}
      trigger={(props) => (
        <button
          type="button"
          {...props}
          aria-label={`Account: ${name}`}
          className={cx(
            'flex min-w-0 items-center gap-2.5 rounded-cn-md p-1.5 text-left transition-colors duration-cn-fast',
            'hover:bg-cn-surface-hover active:bg-cn-surface-active aria-expanded:bg-cn-surface-hover',
            !compact && 'w-full',
            focusRing,
            className,
          )}
        >
          <Avatar name={name} src={src} />
          {!compact && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-cn-label font-semibold text-cn-fg">{name}</span>
                {detail && <span className="block truncate text-cn-caption text-cn-fg-muted">{detail}</span>}
              </span>
              <ChevronsUpDown aria-hidden className="size-4 shrink-0 text-cn-fg-muted" />
            </>
          )}
        </button>
      )}
    />
  );
}
