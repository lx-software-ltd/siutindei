'use client';

import { useEffect, useId, useRef, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export interface AdminDialogProps {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children?: ReactNode;
  /** Custom footer; when omitted, a single primary close button labelled `closeLabel` is rendered. */
  footer?: ReactNode;
  closeLabel?: string;
  dialogRole?: 'dialog' | 'alertdialog';
  contentClassName?: string;
}

export function AdminDialog({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  closeLabel = 'Close',
  dialogRole = 'dialog',
  contentClassName = 'w-full max-w-md',
}: AdminDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousActiveElement =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;

    const focusable = () => {
      const dialog = dialogRef.current;
      if (!dialog) {
        return [];
      }
      return Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
        )
      ).filter((element) => !element.hasAttribute('disabled'));
    };

    focusable()[0]?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key !== 'Tab') {
        return;
      }

      const elements = focusable();
      if (elements.length === 0) {
        return;
      }

      const firstFocusable = elements[0];
      const lastFocusable = elements[elements.length - 1];

      if (event.shiftKey && document.activeElement === firstFocusable) {
        event.preventDefault();
        lastFocusable.focus();
        return;
      }

      if (!event.shiftKey && document.activeElement === lastFocusable) {
        event.preventDefault();
        firstFocusable.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previousActiveElement?.focus();
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className='fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-4'
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        role={dialogRole}
        aria-modal='true'
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        className={contentClassName}
      >
        <Card className='space-y-4'>
          <div className='space-y-2'>
            <h2 id={titleId} className='text-base font-semibold text-slate-900'>
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className='text-sm text-slate-600'>
                {description}
              </p>
            ) : null}
          </div>
          {children}
          {footer === undefined ? (
            <div className='flex justify-end'>
              <Button type='button' variant='primary' onClick={onClose}>
                {closeLabel}
              </Button>
            </div>
          ) : (
            footer
          )}
        </Card>
      </div>
    </div>
  );
}
