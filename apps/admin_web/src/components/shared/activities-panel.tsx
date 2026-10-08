'use client';

import { useEffect, useMemo, useState } from 'react';

import { useActivityCategories } from '../../hooks/use-activity-categories';
import { useExhaustPages } from '../../hooks/use-exhaust-pages';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationScope } from '../../hooks/use-organization-scope';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { parseRequiredNumber } from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/resource-api';
import { normalizeKey } from '../../lib/string-utils';
import {
  buildTranslationsPayload,
  emptyTranslations,
  extractTranslations,
  type LanguageCode,
  type TranslationLanguageCode,
} from '../../lib/translations';
import type { Activity } from '../../types/admin';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid, formErrorClassName } from '../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { AdminFilterBar, AdminFilterField } from '../ui/admin-filter-bar';
import { CascadingCategorySelect } from '../ui/cascading-category-select';
import { Input } from '../ui/input';
import { LanguageToggleInput } from '../ui/language-toggle-input';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { Textarea } from '../ui/textarea';
import { StatusBanner } from '../status-banner';
import { OrganizationWorkspaceTitle } from '../admin/organization-workspace-title';
import { WorkspaceScopeGate } from '../admin/workspace-empty';

interface ActivityFormState {
  org_id: string;
  category_id: string;
  name: string;
  description: string;
  name_translations: Record<TranslationLanguageCode, string>;
  description_translations: Record<TranslationLanguageCode, string>;
  age_min: string;
  age_max: string;
  source_url: string;
  source_note: string;
}

const emptyForm: ActivityFormState = {
  org_id: '',
  category_id: '',
  name: '',
  description: '',
  name_translations: emptyTranslations(),
  description_translations: emptyTranslations(),
  age_min: '',
  age_max: '',
  source_url: '',
  source_note: '',
};

function itemToForm(item: Activity): ActivityFormState {
  return {
    org_id: item.org_id ?? '',
    category_id: item.category_id ?? '',
    name: item.name ?? '',
    description: item.description ?? '',
    name_translations: extractTranslations(item.name_translations),
    description_translations: extractTranslations(item.description_translations),
    age_min: item.age_min !== undefined ? `${item.age_min}` : '',
    age_max: item.age_max !== undefined ? `${item.age_max}` : '',
    source_url: item.source_url ?? '',
    source_note: item.source_note ?? '',
  };
}

interface ActivitiesPanelProps {
  mode: ApiMode;
}

export function ActivitiesPanel({ mode }: ActivitiesPanelProps) {
  const isAdmin = mode === 'admin';
  const scope = useOrganizationScope();
  const scopedOrgId = scope.orgId;
  const { tree: categoryTree } = useActivityCategories();
  const defaultOrgId = scopedOrgId ?? '';
  const resolvedEmptyForm = useMemo(
    () => ({ ...emptyForm, org_id: defaultOrgId }),
    [defaultOrgId]
  );
  const panel = useResourceEditor<Activity, ActivityFormState>({
    resource: 'activities',
    mode,
    emptyForm: resolvedEmptyForm,
    itemToForm,
    paramName: 'activity',
    legacyParam: 'edit',
    listFilters: scopedOrgId ? { org_id: scopedOrgId } : {},
    enabled: Boolean(scopedOrgId),
    noun: 'activity',
  });

  const categoryPathById = useMemo(() => {
    const map = new Map<string, string>();
    function walk(nodes: typeof categoryTree, prefix = '') {
      for (const node of nodes) {
        const path = prefix ? `${prefix} / ${node.name}` : node.name;
        map.set(node.id, path);
        if (node.children) {
          walk(node.children, path);
        }
      }
    }
    walk(categoryTree);
    return map;
  }, [categoryTree]);

  const getCategoryPath = (categoryId?: string) =>
    (categoryId ? categoryPathById.get(categoryId) : undefined) ?? '—';

  const [searchQuery, setSearchQuery] = useState('');
  useExhaustPages(Boolean(searchQuery.trim()), {
    hasMore: panel.hasMore,
    isLoading: panel.isLoading,
    isLoadingMore: panel.isLoadingMore,
    error: panel.listError,
    loadMore: panel.loadMore,
  });

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['org_id', 'name', 'category_id', 'age_min', 'age_max'],
    formKey
  );
  const errorInputClassName = formErrorClassName;
  const { markTouched } = validation;
  const shouldShowError = (field: string, message: string) =>
    validation.shouldShowError(field, Boolean(message));

  const { setFormState } = panel;

  useEffect(() => {
    if (!defaultOrgId || panel.formState.org_id) {
      return;
    }
    if (!panel.isDraftOpen && panel.editingId === null) {
      return;
    }
    setFormState((prev) =>
      prev.org_id ? prev : { ...prev, org_id: defaultOrgId }
    );
  }, [
    defaultOrgId,
    panel.editingId,
    panel.formState.org_id,
    panel.isDraftOpen,
    setFormState,
  ]);

  const validate = () => {
    const ageMin = parseRequiredNumber(panel.formState.age_min);
    const ageMax = parseRequiredNumber(panel.formState.age_max);

    if (!panel.formState.org_id || !panel.formState.name.trim()) {
      return 'Organization and name are required.';
    }
    const normalizedName = normalizeKey(panel.formState.name);
    const hasDuplicate = panel.items.some((item) => {
      if (!item.name) {
        return false;
      }
      if (panel.editingId && item.id === panel.editingId) {
        return false;
      }
      return (
        item.org_id === panel.formState.org_id &&
        normalizeKey(item.name) === normalizedName
      );
    });
    if (hasDuplicate) {
      return 'Activity name must be unique within the organization.';
    }
    if (!panel.formState.category_id) {
      return 'Category is required.';
    }
    if (
      !panel.formState.age_min.trim() ||
      !panel.formState.age_max.trim() ||
      ageMin === null ||
      ageMax === null
    ) {
      return 'Age range must be numeric.';
    }
    if (ageMin >= ageMax) {
      return 'Age min must be less than age max.';
    }
    return null;
  };

  const nameError = useMemo(() => {
    const trimmedName = panel.formState.name.trim();
    if (!trimmedName) {
      return 'Enter an activity name.';
    }
    const normalizedName = normalizeKey(trimmedName);
    const hasDuplicate = panel.items.some((item) => {
      if (!item.name) {
        return false;
      }
      if (panel.editingId && item.id === panel.editingId) {
        return false;
      }
      return (
        item.org_id === panel.formState.org_id &&
        normalizeKey(item.name) === normalizedName
      );
    });
    if (hasDuplicate) {
      return 'Name already exists for this organization.';
    }
    return '';
  }, [
    panel.editingId,
    panel.formState.name,
    panel.formState.org_id,
    panel.items,
  ]);

  const categoryError = panel.formState.category_id
    ? ''
    : 'Select a category.';

  const ageMinValue = parseRequiredNumber(panel.formState.age_min);
  const ageMaxValue = parseRequiredNumber(panel.formState.age_max);
  const ageMinError = useMemo(() => {
    const trimmed = panel.formState.age_min.trim();
    if (!trimmed) {
      return 'Enter a minimum age.';
    }
    return ageMinValue === null ? 'Age min must be numeric.' : '';
  }, [ageMinValue, panel.formState.age_min]);
  const ageMaxError = useMemo(() => {
    const trimmed = panel.formState.age_max.trim();
    if (!trimmed) {
      return 'Enter a maximum age.';
    }
    return ageMaxValue === null ? 'Age max must be numeric.' : '';
  }, [ageMaxValue, panel.formState.age_max]);
  const ageRangeError =
    ageMinValue !== null && ageMaxValue !== null && ageMinValue >= ageMaxValue
      ? 'Age min must be less than age max.'
      : '';

  const handleNameChange = (language: LanguageCode, value: string) => {
    markTouched('name');
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

  const handleDescriptionChange = (language: LanguageCode, value: string) => {
    panel.setFormState((prev) =>
      language === 'en'
        ? { ...prev, description: value }
        : {
            ...prev,
            description_translations: {
              ...prev.description_translations,
              [language]: value,
            },
          }
    );
  };

  const importedLabel =
    panel.items.find((item) => item.id === panel.editingId)
      ?.source_category_name ?? '';

  const formToPayload = (form: ActivityFormState) => ({
    org_id: form.org_id,
    category_id: form.category_id,
    name: form.name.trim(),
    description: form.description.trim() || null,
    name_translations: buildTranslationsPayload(form.name_translations),
    description_translations: buildTranslationsPayload(
      form.description_translations
    ),
    age_min: parseRequiredNumber(form.age_min),
    age_max: parseRequiredNumber(form.age_max),
    ...(isAdmin
      ? {
          source_url: form.source_url.trim() || null,
          source_note: form.source_note.trim() || null,
        }
      : {}),
  });

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

  const filteredItems = panel.items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const nameTranslations = Object.values(item.name_translations ?? {})
      .join(' ')
      .toLowerCase();
    const descriptionTranslations = Object.values(
      item.description_translations ?? {}
    )
      .join(' ')
      .toLowerCase();
    const categoryPath = getCategoryPath(item.category_id).toLowerCase();
    return (
      item.name?.toLowerCase().includes(query) ||
      item.description?.toLowerCase().includes(query) ||
      nameTranslations.includes(query) ||
      descriptionTranslations.includes(query) ||
      categoryPath.includes(query)
    );
  });

  const showNameError = shouldShowError('name', nameError);
  const showCategoryError = shouldShowError('category_id', categoryError);
  const showAgeMinError = shouldShowError('age_min', ageMinError);
  const showAgeMaxError = shouldShowError('age_max', ageMaxError);
  const showAgeRangeError = Boolean(
    ageRangeError &&
      (validation.hasSubmitted ||
        validation.touched.age_min ||
        validation.touched.age_max)
  );

  const detail = (
    <AdminEditorPanel
      status={
        panel.error ? (
          <StatusBanner kind='error'>
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
        <AdminField error={showNameError ? nameError : undefined}>
          <LanguageToggleInput
            id='activity-name'
            label='Name'
            required
            values={{
              en: panel.formState.name,
              zh: panel.formState.name_translations.zh,
              yue: panel.formState.name_translations.yue,
            }}
            onChange={handleNameChange}
            hasError={showNameError}
            inputClassName={showNameError ? errorInputClassName : ''}
          />
        </AdminField>
        <AdminField span={2}>
          <CascadingCategorySelect
            tree={categoryTree}
            value={panel.formState.category_id}
            onChange={(categoryId, _chain) => {
              markTouched('category_id');
              panel.setFormState((prev) => ({
                ...prev,
                category_id: categoryId,
              }));
            }}
            required
            hasError={showCategoryError}
            errorMessage={showCategoryError ? categoryError : undefined}
          />
        </AdminField>
        <AdminField span={2}>
          <LanguageToggleInput
            id='activity-description'
            label='Description'
            multiline
            rows={3}
            values={{
              en: panel.formState.description,
              zh: panel.formState.description_translations.zh,
              yue: panel.formState.description_translations.yue,
            }}
            onChange={handleDescriptionChange}
          />
        </AdminField>
        {isAdmin ? (
          <>
            {importedLabel ? (
              <AdminReadOnlyValue label='Imported as' span={2}>
                {importedLabel}
              </AdminReadOnlyValue>
            ) : null}
            <AdminField label='Source URL' htmlFor='activity-source-url' span={2}>
              <Input
                id='activity-source-url'
                type='url'
                value={panel.formState.source_url}
                onChange={(event) =>
                  panel.setFormState((prev) => ({
                    ...prev,
                    source_url: event.target.value,
                  }))
                }
                placeholder='https://'
              />
            </AdminField>
            <AdminField label='Source note' htmlFor='activity-source-note' span={2}>
              <Textarea
                id='activity-source-note'
                rows={2}
                value={panel.formState.source_note}
                onChange={(event) =>
                  panel.setFormState((prev) => ({
                    ...prev,
                    source_note: event.target.value,
                  }))
                }
              />
            </AdminField>
          </>
        ) : null}
        <AdminField
          label='Age Min'
          htmlFor='activity-age-min'
          required
          error={showAgeMinError ? ageMinError : undefined}
        >
          <Input
            id='activity-age-min'
            type='number'
            min='0'
            value={panel.formState.age_min}
            onChange={(e) => {
              markTouched('age_min');
              panel.setFormState((prev) => ({
                ...prev,
                age_min: e.target.value,
              }));
            }}
            className={
              showAgeMinError || showAgeRangeError
                ? errorInputClassName
                : ''
            }
            aria-invalid={
              showAgeMinError || showAgeRangeError || undefined
            }
          />
        </AdminField>
        <AdminField
          label='Age Max'
          htmlFor='activity-age-max'
          required
          error={
            showAgeMaxError
              ? ageMaxError
              : showAgeRangeError
                ? ageRangeError
                : undefined
          }
        >
          <Input
            id='activity-age-max'
            type='number'
            min='0'
            value={panel.formState.age_max}
            onChange={(e) => {
              markTouched('age_max');
              panel.setFormState((prev) => ({
                ...prev,
                age_max: e.target.value,
              }));
            }}
            className={
              showAgeMaxError || showAgeRangeError
                ? errorInputClassName
                : ''
            }
            aria-invalid={
              showAgeMaxError || showAgeRangeError || undefined
            }
          />
        </AdminField>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <WorkspaceScopeGate orgId={scopedOrgId} isAdmin={isAdmin} noun='activities'>
      <div className='space-y-4'>
        <OrganizationWorkspaceTitle mode={mode} orgId={scopedOrgId} />
        <ResourceTableShell
        ariaLabel={isAdmin ? 'Activities' : 'Your activities'}
        rows={filteredItems}
        getLabel={(item) => item.name || 'Activity'}
        middleColumnCount={3}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel={
          searchQuery.trim()
            ? 'No activities match your search.'
            : 'No activities yet.'
        }
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New activity'
        onToggleDraft={panel.collapse}
        detail={detail}
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New activity'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          >
            <AdminFilterField>
              <Input
                id='activity-search'
                placeholder='Search activities...'
                aria-label='Search activities'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Name</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Category
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Age Range
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              {item.name}
              <AdminDataTableCellMeta until='secondary'>
                {getCategoryPath(item.category_id)}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {getCategoryPath(item.category_id)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {`${item.age_min} - ${item.age_max}`}
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) =>
          deleteRowActions(() => panel.handleDelete(item))
        }
      />
        {panel.confirmDialog}
      </div>
    </WorkspaceScopeGate>
  );
}
