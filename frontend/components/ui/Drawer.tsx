'use client';

import { type ReactNode, type RefObject, useId } from 'react';

import { cx } from '@/lib/design/styles';

import { ModalFooter, ModalHeader, ModalLayer } from './ModalLayer';

export type DrawerSide = 'right' | 'left' | 'bottom';

const PLACEMENT: Record<DrawerSide, { container: string; panel: string }> = {
  right: { container: 'justify-end', panel: 'h-full w-full rounded-l-cn-xl border-r-0' },
  left: { container: 'justify-start', panel: 'h-full w-full rounded-r-cn-xl border-l-0' },
  bottom: { container: 'items-end', panel: 'max-h-[90dvh] w-full rounded-t-cn-xl border-b-0' },
};

const WIDTH = { sm: 'max-w-xs', md: 'max-w-[26rem]', lg: 'max-w-xl' } as const;

export interface DrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  /** `bottom` is the phone sheet (prompt bar, filters). */
  side?: DrawerSide;
  /** Width for side drawers. */
  size?: keyof typeof WIDTH;
  initialFocusRef?: RefObject<HTMLElement | null>;
  className?: string;
}

/**
 * A modal panel from the edge: version history, notifications, mobile
 * navigation, the phone prompt sheet. Same focus rules as Dialog.
 */
export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  side = 'right',
  size = 'md',
  initialFocusRef,
  className,
}: DrawerProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const descriptionId = description ? `${id}-description` : undefined;
  const close = () => onOpenChange(false);

  return (
    <ModalLayer
      open={open}
      onClose={close}
      labelledBy={titleId}
      describedBy={descriptionId}
      initialFocusRef={initialFocusRef}
      layer="drawer"
      motion={`sheet-${side}`}
      placement={PLACEMENT[side].container}
      panelClassName={cx(PLACEMENT[side].panel, side !== 'bottom' && WIDTH[size], className)}
    >
      <ModalHeader titleId={titleId} descriptionId={descriptionId} title={title} description={description} onClose={close} />
      {children && <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">{children}</div>}
      {footer && <ModalFooter>{footer}</ModalFooter>}
    </ModalLayer>
  );
}
