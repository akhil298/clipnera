'use client';

import { type ReactNode, type RefObject, useId } from 'react';

import { cx } from '@/lib/design/styles';

import { ModalFooter, ModalHeader, ModalLayer } from './ModalLayer';

const WIDTH = { sm: 'sm:max-w-sm', md: 'sm:max-w-lg', lg: 'sm:max-w-2xl' } as const;

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  /** One or two sentences; read by screen readers when the dialog opens. */
  description?: ReactNode;
  children?: ReactNode;
  /** Buttons. Put the primary action last. */
  footer?: ReactNode;
  size?: keyof typeof WIDTH;
  /** `alertdialog` for a confirmation that must be answered (delete, spend credits). */
  role?: 'dialog' | 'alertdialog';
  /** Escape and backdrop close it. Default true. Turn off only while a required step is in flight. */
  dismissible?: boolean;
  /** Where focus lands on open. Default: an element with `data-autofocus`, else the first control. */
  initialFocusRef?: RefObject<HTMLElement | null>;
  hideCloseButton?: boolean;
  className?: string;
}

/**
 * A modal dialog: centred on larger screens, a bottom sheet on phones. Focus
 * is trapped inside and returns to the trigger on close.
 */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = 'md',
  role = 'dialog',
  dismissible = true,
  initialFocusRef,
  hideCloseButton = false,
  className,
}: DialogProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const descriptionId = description ? `${id}-description` : undefined;
  const close = () => onOpenChange(false);

  return (
    <ModalLayer
      open={open}
      onClose={close}
      role={role}
      labelledBy={titleId}
      describedBy={descriptionId}
      dismissible={dismissible}
      initialFocusRef={initialFocusRef}
      layer="dialog"
      motion="pop"
      placement="items-end justify-center sm:items-center sm:p-4"
      panelClassName={cx('max-h-[90dvh] w-full rounded-t-cn-xl sm:rounded-cn-xl', WIDTH[size], className)}
    >
      <ModalHeader
        titleId={titleId}
        descriptionId={descriptionId}
        title={title}
        description={description}
        onClose={hideCloseButton || !dismissible ? undefined : close}
      />
      {children && <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">{children}</div>}
      {footer && <ModalFooter>{footer}</ModalFooter>}
    </ModalLayer>
  );
}
