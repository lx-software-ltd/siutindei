'use client';

import type { ReactNode } from 'react';

import { AdminDialog } from './admin-dialog';
import { Button } from './button';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: 'danger' | 'default';
  children?: ReactNode;
  confirmDisabled?: boolean;
  confirmLoading?: boolean;
  confirmLoadingLabel?: string;
}

/**
 * Confirm or cancel. Built on `AdminDialog` so overlay, title, focus trap,
 * and escape behaviour stay the same as every other dialog.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'default',
  children,
  confirmDisabled = false,
  confirmLoading = false,
  confirmLoadingLabel,
}: ConfirmDialogProps) {
  return (
    <AdminDialog
      open={open}
      title={title}
      description={message}
      onClose={onCancel}
      dialogRole='alertdialog'
      footer={
        <div className='flex justify-end gap-3'>
          <Button type='button' variant='secondary' onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            type='button'
            variant={variant === 'danger' ? 'danger' : 'primary'}
            disabled={confirmDisabled}
            loading={confirmLoading}
            loadingLabel={confirmLoadingLabel}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      }
    >
      {children}
    </AdminDialog>
  );
}
