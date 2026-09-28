'use client';

import type { UseExpandedRecordReturn } from '@/hooks/use-expanded-record';

import { ConfirmDialog } from './confirm-dialog';

export interface AdminDiscardChangesDialogProps {
  prompt: UseExpandedRecordReturn['discardPrompt'];
}

/** Confirms leaving an expanded editor that has unsaved edits. */
export function AdminDiscardChangesDialog({
  prompt,
}: AdminDiscardChangesDialogProps) {
  return (
    <ConfirmDialog
      open={prompt.open}
      title='Discard unsaved changes?'
      message='The open record has edits that have not been saved. Discard them and switch records?'
      confirmLabel='Discard changes'
      cancelLabel='Keep editing'
      variant='danger'
      onConfirm={prompt.confirm}
      onCancel={prompt.cancel}
    />
  );
}
