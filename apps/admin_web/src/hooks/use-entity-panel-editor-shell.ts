'use client';

import { useCallback, useRef, useState } from 'react';

import { useConfirmDialog } from '@/hooks/use-confirm-dialog';
import {
  DRAFT_RECORD_ID,
  useExpandedRecord,
} from '@/hooks/use-expanded-record';

export interface UseEntityPanelEditorShellOptions {
  paramName: string;
  legacyParam?: string;
  onExpandedChange?: (expandedId: string | null) => void;
}

/**
 * Shared state for a table-first entity editor: one expanded row, a dirty
 * flag that guards row switches, and the confirm dialog used by deletes.
 */
export function useEntityPanelEditorShell({
  paramName,
  legacyParam,
  onExpandedChange,
}: UseEntityPanelEditorShellOptions) {
  const { confirm, confirmDialog } = useConfirmDialog();
  const [deleteActionError, setDeleteActionError] = useState('');
  const dirtyRef = useRef(false);

  const expanded = useExpandedRecord({
    paramName,
    legacyParam,
    isDirty: () => dirtyRef.current,
    onChange: onExpandedChange,
  });

  const markDirty = useCallback(() => {
    dirtyRef.current = true;
  }, []);
  const clearDirty = useCallback(() => {
    dirtyRef.current = false;
  }, []);

  const selectedId =
    expanded.expandedId && expanded.expandedId !== DRAFT_RECORD_ID
      ? expanded.expandedId
      : null;
  const editorMode: 'create' | 'edit' = selectedId ? 'edit' : 'create';

  return {
    confirm,
    confirmDialog,
    deleteActionError,
    setDeleteActionError,
    editorMode,
    selectedId,
    expanded,
    markDirty,
    clearDirty,
  };
}
