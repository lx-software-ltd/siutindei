'use client';

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactElement,
  type SetStateAction,
} from 'react';

import { AdminDiscardChangesDialog } from '@/components/ui/admin-discard-changes-dialog';
import { useEntityPanelEditorShell } from '@/hooks/use-entity-panel-editor-shell';
import { useExpandedRecordForm } from '@/hooks/use-expanded-record-form';
import { usePaginatedList } from '@/hooks/use-paginated-list';
import { ApiError } from '@/lib/api-client-core';
import { ADMIN_LIST_PAGE_SIZE } from '@/lib/admin-list-query';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import {
  getResourceApi,
  type ApiMode,
  type ResourceType,
} from '@/lib/resource-api';

interface UseResourceEditorOptions<T extends { id: string }, TForm> {
  resource: ResourceType;
  mode: ApiMode;
  emptyForm: TForm;
  itemToForm: (item: T) => TForm;
  /** URL parameter for the open row, for example `organization`. */
  paramName: string;
  /**
   * Read `?edit=` until the next expansion change. Used by organizations,
   * locations, activities, pricing, and schedules.
   */
  legacyParam?: string;
  /** Open the first row once when the list arrives (manager organizations). */
  autoExpandFirst?: boolean;
  /** Load every page (category tree). Stops at `ADMIN_LIST_AUTO_PAGE_CAP`. */
  fetchAll?: boolean;
  limit?: number;
  noun: string;
}

/**
 * Cursor-paginated list plus the single expanded editor for one admin
 * resource. Replaces the hand-rolled `useResourcePanel` fetch loop.
 */
export function useResourceEditor<T extends { id: string }, TForm>({
  resource,
  mode,
  emptyForm,
  itemToForm,
  paramName,
  legacyParam,
  autoExpandFirst = false,
  fetchAll = false,
  limit = ADMIN_LIST_PAGE_SIZE,
  noun,
}: UseResourceEditorOptions<T, TForm>) {
  const api = useMemo(
    () => getResourceApi<T>(resource, mode),
    [resource, mode]
  );
  const shell = useEntityPanelEditorShell({ paramName, legacyParam });
  const [formState, setFormStateRaw] = useState<TForm>(emptyForm);
  const [saveError, setSaveError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [pinnedCreated, setPinnedCreated] = useState<T | null>(null);
  const [missingNotice, setMissingNotice] = useState('');
  const formStateRef = useRef(formState);
  const emptyFormRef = useRef(emptyForm);
  const itemToFormRef = useRef(itemToForm);
  formStateRef.current = formState;
  emptyFormRef.current = emptyForm;
  itemToFormRef.current = itemToForm;

  const list = usePaginatedList<T, Record<string, never>>({
    queryKey: adminQueryKeys.resourceList(resource, mode),
    defaultFilters: {},
    fetchAll,
    limit,
    errorPrefix: `Failed to load ${resource}`,
    fetcher: async ({ cursor, limit, signal }) => {
      const response = await api.list(cursor ?? undefined, limit, signal);
      return {
        items: response.items,
        nextCursor: response.next_cursor ?? null,
      };
    },
  });

  const rows = useMemo(() => {
    if (
      pinnedCreated &&
      !list.items.some((item) => item.id === pinnedCreated.id)
    ) {
      return [pinnedCreated, ...list.items];
    }
    return list.items;
  }, [list.items, pinnedCreated]);

  const { pinnedRow } = useExpandedRecordForm<T>({
    expandedId: shell.expanded.expandedId,
    rows,
    isLoading: list.isLoading,
    applyRow: (row) => {
      setMissingNotice('');
      setFormStateRaw(itemToFormRef.current(row));
      shell.clearDirty();
      setSaveError('');
    },
    reset: () => {
      setFormStateRaw(emptyFormRef.current);
      shell.clearDirty();
      setSaveError('');
    },
    collapse: shell.expanded.collapse,
    fetchMissing: async (id) => {
      try {
        return await api.get(id);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          return null;
        }
        throw err;
      }
    },
    onMissing: () => {
      setMissingNotice('That record could not be opened. It may have been deleted.');
    },
  });

  const items = useMemo(() => {
    if (pinnedRow && !rows.some((item) => item.id === pinnedRow.id)) {
      return [pinnedRow, ...rows];
    }
    return rows;
  }, [pinnedRow, rows]);

  const {
    confirm,
    confirmDialog: deleteConfirmDialog,
    expanded,
    selectedId,
    markDirty,
    clearDirty,
    editorMode,
  } = shell;
  const expand = expanded.expand;
  const collapse = expanded.collapse;
  const expandedId = expanded.expandedId;

  useEffect(() => {
    if (expandedId) {
      setMissingNotice('');
    }
  }, [expandedId]);

  const didAutoExpand = useRef(false);
  useEffect(() => {
    if (!autoExpandFirst || didAutoExpand.current || list.isLoading) {
      return;
    }
    didAutoExpand.current = true;
    if (!expandedId && list.items[0]) {
      expand(list.items[0].id);
    }
  }, [autoExpandFirst, expand, expandedId, list.isLoading, list.items]);

  const setFormState: Dispatch<SetStateAction<TForm>> = useCallback(
    (update) => {
      markDirty();
      setFormStateRaw(update);
    },
    [markDirty]
  );

  const handleSubmit = useCallback(
    async (
      formToPayload: (form: TForm) => unknown,
      validate?: () => string | null
    ) => {
      if (validate) {
        const validationError = validate();
        if (validationError) {
          setSaveError(validationError);
          return;
        }
      }
      setIsSaving(true);
      setSaveError('');
      try {
        const payload = formToPayload(formStateRef.current);
        if (selectedId) {
          const updated = await api.update(selectedId, payload);
          list.setItems((prev) =>
            prev.map((item) => (item.id === selectedId ? updated : item))
          );
          setFormStateRaw(itemToFormRef.current(updated));
          clearDirty();
        } else if (api.create) {
          const created = await api.create(payload);
          setPinnedCreated(created);
          list.setItems((prev) => [
            created,
            ...prev.filter((item) => item.id !== created.id),
          ]);
          clearDirty();
          expand(created.id);
        } else {
          setSaveError('Creating new items is not allowed.');
        }
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : `Unable to save ${noun}.`;
        setSaveError(message);
      } finally {
        setIsSaving(false);
      }
    },
    [api, clearDirty, expand, list, noun, selectedId]
  );

  const handleDelete = useCallback(
    async (item: T & { name?: string }) => {
      const displayName = item.name || item.id;
      const confirmed = await confirm(
        `Delete ${noun} "${displayName}"?`,
        'This action cannot be undone.',
        { variant: 'danger', confirmLabel: 'Delete' }
      );
      if (!confirmed) {
        return;
      }
      setSaveError('');
      try {
        await api.delete(item.id);
        setPinnedCreated((current) => (current?.id === item.id ? null : current));
        list.setItems((prev) => prev.filter((entry) => entry.id !== item.id));
        if (expandedId === item.id) {
          clearDirty();
          collapse();
        }
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : `Unable to delete ${noun}.`;
        setSaveError(message);
      }
    },
    [api, clearDirty, collapse, confirm, expandedId, list, noun]
  );

  const confirmDialog: ReactElement = (
    <>
      {deleteConfirmDialog}
      <AdminDiscardChangesDialog prompt={expanded.discardPrompt} />
    </>
  );

  return {
    items,
    hasMore: list.hasMore,
    isLoading: list.isLoading,
    isLoadingMore: list.isLoadingMore,
    loadMore: list.loadMore,
    isSaving,
    error: saveError,
    listError: list.error || missingNotice,
    setError: setSaveError,
    editingId: selectedId,
    editorMode,
    formState,
    setFormState,
    isDraftOpen: expanded.isDraftOpen,
    isExpanded: expanded.isExpanded,
    toggle: expanded.toggle,
    openDraft: expanded.openDraft,
    collapse,
    startEdit: (item: T) => {
      expand(item.id);
    },
    resetForm: () => {
      clearDirty();
      collapse();
    },
    handleSubmit,
    handleDelete,
    confirmDialog,
    canCreate: Boolean(api.create),
  };
}
