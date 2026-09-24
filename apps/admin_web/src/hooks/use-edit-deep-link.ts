'use client';

import { useEffect } from 'react';
import { useQueryState } from 'nuqs';

export function useEditDeepLink<T extends { id: string }>(
  items: T[],
  editingId: string | null,
  startEdit: (item: T) => void
) {
  const [editId] = useQueryState('edit');

  useEffect(() => {
    if (!editId || editingId === editId) {
      return;
    }
    const match = items.find((item) => item.id === editId);
    if (match) {
      startEdit(match);
    }
  }, [editId, editingId, items, startEdit]);
}
