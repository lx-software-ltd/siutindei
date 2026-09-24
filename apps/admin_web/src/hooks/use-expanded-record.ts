'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryState } from 'nuqs';

export const DRAFT_RECORD_ID = 'new';

export interface UseExpandedRecordOptions {
  /** Query parameter that mirrors the open record so deep links restore it. */
  paramName?: string;
  /**
   * Older deep links used `?edit=<id>`. When set, that parameter is read as
   * a fallback and cleared the next time the expansion changes.
   */
  legacyParam?: string;
  /** Return true when the open editor has unsaved changes. */
  isDirty?: () => boolean;
  /** Called after the open record changes (including to `null`). */
  onChange?: (expandedId: string | null) => void;
}

export interface UseExpandedRecordReturn {
  expandedId: string | null;
  isDraftOpen: boolean;
  isExpanded: (id: string) => boolean;
  toggle: (id: string) => void;
  expand: (id: string) => void;
  openDraft: () => void;
  collapse: () => void;
  discardPrompt: {
    open: boolean;
    confirm: () => void;
    cancel: () => void;
  };
}

/**
 * Single-open expansion state for a record table, stored in `?<param>=<id>`.
 * Only one row (or the draft row) is expanded at a time. A dirty editor must
 * be confirmed before another row replaces it.
 */
export function useExpandedRecord({
  paramName = 'record',
  legacyParam,
  isDirty,
  onChange,
}: UseExpandedRecordOptions = {}): UseExpandedRecordReturn {
  const [fromUrl, setFromUrl] = useQueryState(paramName);
  const [legacyValue, setLegacyValue] = useQueryState(legacyParam ?? 'edit');
  const expandedId = fromUrl || (legacyParam ? legacyValue : null) || null;
  const [pendingTarget, setPendingTarget] = useState<string | null | undefined>(
    undefined
  );
  const isDirtyRef = useRef(isDirty);
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    isDirtyRef.current = isDirty;
    onChangeRef.current = onChange;
  });

  const apply = useCallback(
    (next: string | null) => {
      void setFromUrl(next);
      if (legacyParam) {
        void setLegacyValue(null);
      }
      onChangeRef.current?.(next);
    },
    [legacyParam, setFromUrl, setLegacyValue]
  );

  const request = useCallback(
    (next: string | null) => {
      if (next === expandedId) {
        return;
      }
      if (expandedId !== null && isDirtyRef.current?.()) {
        setPendingTarget(next);
        return;
      }
      apply(next);
    },
    [apply, expandedId]
  );

  const toggle = useCallback(
    (id: string) => {
      request(expandedId === id ? null : id);
    },
    [expandedId, request]
  );

  const discardPrompt = useMemo(
    () => ({
      open: pendingTarget !== undefined,
      confirm: () => {
        if (pendingTarget !== undefined) {
          apply(pendingTarget);
        }
        setPendingTarget(undefined);
      },
      cancel: () => {
        setPendingTarget(undefined);
      },
    }),
    [apply, pendingTarget]
  );

  return {
    expandedId,
    isDraftOpen: expandedId === DRAFT_RECORD_ID,
    isExpanded: useCallback((id: string) => expandedId === id, [expandedId]),
    toggle,
    expand: useCallback((id: string) => request(id), [request]),
    openDraft: useCallback(() => request(DRAFT_RECORD_ID), [request]),
    collapse: useCallback(() => request(null), [request]),
    discardPrompt,
  };
}
