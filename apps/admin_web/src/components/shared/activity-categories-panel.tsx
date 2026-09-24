'use client';

import { useMemo, useState } from 'react';

import { useFormValidation } from '../../hooks/use-form-validation';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { ADMIN_API_MAX_LIST_LIMIT } from '../../lib/admin-list-query';
import {
  buildTranslationsPayload,
  emptyTranslations,
  extractTranslations,
  type LanguageCode,
  type TranslationLanguageCode,
} from '../../lib/translations';
import type { ActivityCategory } from '../../types/admin';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminFilterBar, AdminFilterField } from '../ui/admin-filter-bar';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { LanguageToggleInput } from '../ui/language-toggle-input';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { Select } from '../ui/select';
import { StatusBanner } from '../status-banner';

interface ActivityCategoryFormState {
  name: string;
  name_translations: Record<TranslationLanguageCode, string>;
  parent_id: string;
  display_order: string;
}

const emptyForm: ActivityCategoryFormState = {
  name: '',
  name_translations: emptyTranslations(),
  parent_id: '',
  display_order: '0',
};

function itemToForm(item: ActivityCategory): ActivityCategoryFormState {
  return {
    name: item.name ?? '',
    name_translations: extractTranslations(item.name_translations),
    parent_id: item.parent_id ?? '',
    display_order:
      item.display_order !== undefined ? `${item.display_order}` : '0',
  };
}

function parseDisplayOrder(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return 0;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
    return null;
  }
  return parsed;
}

export function ActivityCategoriesPanel() {
  const panel = useResourceEditor<ActivityCategory, ActivityCategoryFormState>({
    resource: 'activity-categories',
    mode: 'admin',
    emptyForm,
    itemToForm,
    paramName: 'category',
    fetchAll: true,
    limit: ADMIN_API_MAX_LIST_LIMIT,
    noun: 'category',
  });

  const [searchQuery, setSearchQuery] = useState('');
  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['name', 'display_order'],
    formKey
  );

  const childrenByParent = useMemo(() => {
    const map = new Map<string, ActivityCategory[]>();
    for (const category of panel.items) {
      const parentId = category.parent_id ?? '';
      const list = map.get(parentId) ?? [];
      list.push(category);
      map.set(parentId, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => {
        const order = (a.display_order ?? 0) - (b.display_order ?? 0);
        if (order !== 0) return order;
        return a.name.localeCompare(b.name);
      });
    }
    return map;
  }, [panel.items]);

  const categoryPathById = useMemo(() => {
    const map = new Map<string, string>();
    function walk(nodes: ActivityCategory[], prefix = '') {
      for (const node of nodes) {
        const path = prefix ? `${prefix} / ${node.name}` : node.name;
        map.set(node.id, path);
        const children = childrenByParent.get(node.id) ?? [];
        walk(children, path);
      }
    }
    const roots = childrenByParent.get('') ?? [];
    walk(roots);
    return map;
  }, [childrenByParent]);

  const excludedIds = useMemo(() => {
    if (!panel.editingId) return new Set<string>();
    const excluded = new Set<string>([panel.editingId]);
    const stack = [panel.editingId];
    while (stack.length > 0) {
      const current = stack.pop() ?? '';
      const children = childrenByParent.get(current) ?? [];
      for (const child of children) {
        if (excluded.has(child.id)) continue;
        excluded.add(child.id);
        stack.push(child.id);
      }
    }
    return excluded;
  }, [panel.editingId, childrenByParent]);

  const parentOptions = useMemo(() => {
    const options: { id: string; label: string }[] = [];
    function walk(nodes: ActivityCategory[], prefix = '') {
      for (const node of nodes) {
        const path = prefix ? `${prefix} / ${node.name}` : node.name;
        if (!excludedIds.has(node.id) && !node.is_system) {
          options.push({ id: node.id, label: path });
        }
        const children = childrenByParent.get(node.id) ?? [];
        walk(children, path);
      }
    }
    const roots = childrenByParent.get('') ?? [];
    walk(roots);
    return options;
  }, [childrenByParent, excludedIds]);

  const editingCategory = panel.items.find(
    (item) => item.id === panel.editingId
  );
  const isSystemLocked = Boolean(editingCategory?.is_system);

  const validate = () => {
    if (!panel.formState.name.trim()) {
      return 'Name is required.';
    }
    const order = parseDisplayOrder(panel.formState.display_order);
    if (order === null || order < 0) {
      return 'Display order must be a valid number.';
    }
    return null;
  };

  const nameError = panel.formState.name.trim()
    ? ''
    : 'Enter a category name.';

  const displayOrderError = useMemo(() => {
    const order = parseDisplayOrder(panel.formState.display_order);
    if (order === null || order < 0) {
      return 'Display order must be a whole number.';
    }
    return '';
  }, [panel.formState.display_order]);

  const handleNameChange = (language: LanguageCode, value: string) => {
    if (isSystemLocked) {
      return;
    }
    validation.markTouched('name');
    panel.setFormState((prev) =>
      language === 'en'
        ? { ...prev, name: value }
        : {
            ...prev,
            name_translations: {
              ...prev.name_translations,
              [language]: value,
            },
          }
    );
  };

  const formToPayload = (form: ActivityCategoryFormState) => {
    const displayOrder = parseDisplayOrder(form.display_order);
    if (isSystemLocked) {
      return { display_order: displayOrder };
    }
    return {
      name: form.name.trim(),
      name_translations: buildTranslationsPayload(form.name_translations),
      parent_id: form.parent_id || null,
      display_order: displayOrder,
    };
  };

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

  const filteredItems = panel.items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const path = categoryPathById.get(item.id)?.toLowerCase() ?? '';
    const nameTranslations = Object.values(item.name_translations ?? {})
      .join(' ')
      .toLowerCase();
    return (
      path.includes(query) ||
      item.name.toLowerCase().includes(query) ||
      nameTranslations.includes(query)
    );
  });

  const showNameError = validation.shouldShowError(
    'name',
    Boolean(nameError)
  );
  const showDisplayOrderError = validation.shouldShowError(
    'display_order',
    Boolean(displayOrderError)
  );

  const detail = (
    <AdminEditorPanel
      status={
        panel.error ? (
          <StatusBanner variant='error' title='Error'>
            {panel.error}
          </StatusBanner>
        ) : null
      }
      actions={
        <AdminEditorActions
          mode={panel.editorMode}
          onSubmit={handleSubmit}
          isSaving={panel.isSaving}
        />
      }
    >
      <AdminFieldGrid columns={2}>
        <div className='space-y-1'>
          <LanguageToggleInput
            id='category-name'
            label='Name'
            required
            readOnly={isSystemLocked}
            values={{
              en: panel.formState.name,
              zh: panel.formState.name_translations.zh,
              yue: panel.formState.name_translations.yue,
            }}
            onChange={handleNameChange}
            hasError={showNameError}
            inputClassName={
              isSystemLocked
                ? 'bg-slate-100'
                : validation.errorClassName('name', Boolean(nameError))
            }
          />
          {showNameError ? (
            <p className='text-xs text-red-600'>{nameError}</p>
          ) : null}
        </div>
        <div>
          <Label htmlFor='category-parent'>Parent</Label>
          <Select
            id='category-parent'
            value={panel.formState.parent_id}
            disabled={isSystemLocked}
            aria-readonly={isSystemLocked || undefined}
            onChange={(e) => {
              if (isSystemLocked) {
                return;
              }
              panel.setFormState((prev) => ({
                ...prev,
                parent_id: e.target.value,
              }));
            }}
          >
            <option value=''>No parent (root)</option>
            {parentOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </Select>
        </div>
        <div className='space-y-1'>
          <Label htmlFor='category-order'>Display Order</Label>
          <Input
            id='category-order'
            type='number'
            min='0'
            step='1'
            value={panel.formState.display_order}
            onChange={(e) => {
              validation.markTouched('display_order');
              panel.setFormState((prev) => ({
                ...prev,
                display_order: e.target.value,
              }));
            }}
            className={validation.errorClassName(
              'display_order',
              Boolean(displayOrderError)
            )}
            aria-invalid={showDisplayOrderError || undefined}
          />
          {showDisplayOrderError ? (
            <p className='text-xs text-red-600'>{displayOrderError}</p>
          ) : null}
        </div>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <>
      <ResourceTableShell
        ariaLabel='Categories'
        rows={filteredItems}
        getLabel={(item) => {
          const label = categoryPathById.get(item.id) || item.name;
          return item.is_system ? `${label} (pending)` : label;
        }}
        middleColumnCount={2}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel={
          searchQuery.trim()
            ? 'No categories match your search.'
            : 'No categories yet.'
        }
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New category'
        onToggleDraft={panel.collapse}
        detail={detail}
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New category'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          >
            <AdminFilterField label='Search' htmlFor='category-search'>
              <Input
                id='category-search'
                placeholder='Search categories...'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Path</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Display Order
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => {
          const label = categoryPathById.get(item.id) || item.name;
          const pathLabel = item.is_system ? `${label} (pending)` : label;
          return (
            <>
              <AdminDataTableCell>
                {pathLabel}
                <AdminDataTableCellMeta until='secondary'>
                  {item.display_order ?? 0}
                </AdminDataTableCellMeta>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                {item.display_order ?? 0}
              </AdminDataTableCell>
            </>
          );
        }}
        renderActions={(item) =>
          item.is_system ? null : deleteRowActions(() => panel.handleDelete(item))
        }
      />
      {panel.confirmDialog}
    </>
  );
}
