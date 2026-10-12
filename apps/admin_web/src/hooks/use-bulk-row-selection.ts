'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export type BulkSelectScope = 'none' | 'some' | 'visible' | 'all';

export function useBulkRowSelection<T extends { id: string }>(
  items: T[],
  hasMore: boolean
) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectScope, setSelectScope] = useState<BulkSelectScope>('none');
  const selectAllRef = useRef<HTMLInputElement>(null);
  const selectedIds = useMemo(() => {
    if (selectScope !== 'visible') {
      return selected;
    }
    return new Set(items.map((item) => item.id));
  }, [items, selectScope, selected]);

  const resetSelection = useCallback(() => {
    setSelected(new Set());
    setSelectScope('none');
  }, []);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate =
        selectScope === 'some' || (selectScope === 'visible' && hasMore);
    }
  }, [hasMore, selectScope]);

  const cycleHeader = useCallback(() => {
    setSelectScope((currentScope) => {
      if (currentScope === 'none' || currentScope === 'some') {
        setSelected(new Set(items.map((item) => item.id)));
        return 'visible';
      }
      if (currentScope === 'visible' && hasMore) {
        return 'all';
      }
      setSelected(new Set());
      return 'none';
    });
  }, [hasMore, items]);

  const toggleRow = useCallback(
    (id: string, checked: boolean) => {
      const base =
        selectScope === 'visible' || selectScope === 'all'
          ? new Set(items.map((item) => item.id))
          : selected;
      const next = new Set(base);
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      setSelected(next);
      setSelectScope(next.size === 0 ? 'none' : 'some');
    },
    [items, selectScope, selected]
  );

  const headerChecked = selectScope === 'all' || selectScope === 'visible';
  const headerLabel =
    selectScope === 'all'
      ? 'Clear selection'
      : selectScope === 'visible' && hasMore
        ? 'Select all matching rows'
        : 'Select visible rows';

  return {
    selected: selectedIds,
    selectScope,
    selectAllRef,
    headerChecked,
    headerLabel,
    cycleHeader,
    toggleRow,
    resetSelection,
  };
}
