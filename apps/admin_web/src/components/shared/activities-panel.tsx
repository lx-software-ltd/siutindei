'use client';

import { useEffect, useMemo } from 'react';

import { useActivityCategories } from '../../hooks/use-activity-categories';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationScope } from '../../hooks/use-organization-scope';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { formatAdminPageName } from '../../lib/admin-page-name';
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
  AdminTableName,
  AdminTableNumber,
  formatAdminTableRange,
} from '../ui/admin-table-value';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid, formErrorClassName } from '../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { CascadingCategorySelect } from '../ui/cascading-category-select';
import { Input } from '../ui/input';
import { LanguageToggleInput } from '../ui/language-toggle-input';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { Textarea } from '../ui/textarea';
import { StatusBanner } from '../status-banner';
import { activityFormFromSnapshot } from '../admin/catalog-version-snapshot';
import { OrganizationWorkspaceTitle } from '../admin/organization-workspace-title';
import {
  HistoricalRowMark,
  useCatalogVersion,
  VersionField,
  VersionFields,
  VersionSwitcher,
  VersionViewBanner,
} from '../admin/version-history';
import { Button } from '../ui/button';
import { WorkspaceScopeGate } from '../admin/workspace-empty';

const PAGE_NAME = formatAdminPageName('Activities');

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
  const versionView = useCatalogVersion({
    mode,
    entityType: 'activity',
    entityId: panel.editingId,
    version: panel.items.find((item) => item.id === panel.editingId)?.version,
  });
  const locked = versionView.locked;
  const editorForm = versionView.snapshot
    ? activityFormFromSnapshot(versionView.snapshot, panel.formState)
    : panel.formState;

  const detail = (
    <AdminEditorPanel
      accessory={
        panel.editingId ? <VersionSwitcher view={versionView} /> : undefined
      }
      status={
        panel.error ? (
          <StatusBanner kind='error'>
            {panel.error}
          </StatusBanner>
        ) : null
      }
      actions={
        versionView.isHistorical ? (
          <Button type='button' variant='secondary' onClick={versionView.backToLatest}>
            Back to latest
          </Button>
        ) : (
          <AdminEditorActions
            mode={panel.editorMode}
            onSubmit={handleSubmit}
            isSaving={panel.isSaving}
          />
        )
      }
    >
      <VersionFields view={versionView}>
      <div className='space-y-4'>
      <VersionViewBanner view={versionView} />
      <AdminFieldGrid columns={2}>
        <VersionField
          versionKey={['name', 'name_translations']}
          error={showNameError ? nameError : undefined}
        >
          <LanguageToggleInput
            id='activity-name'
            label='Name'
            required
            readOnly={locked}
            values={{
              en: editorForm.name,
              zh: editorForm.name_translations.zh,
              yue: editorForm.name_translations.yue,
            }}
            onChange={handleNameChange}
            hasError={showNameError}
            inputClassName={showNameError ? errorInputClassName : ''}
          />
        </VersionField>
        <VersionField span={2}>
          <CascadingCategorySelect
            tree={categoryTree}
            value={editorForm.category_id}
            onChange={(categoryId, _chain) => {
              markTouched('category_id');
              panel.setFormState((prev) => ({
                ...prev,
                category_id: categoryId,
              }));
            }}
            disabled={locked}
            required
            hasError={showCategoryError}
            errorMessage={showCategoryError ? categoryError : undefined}
          />
        </VersionField>
        <VersionField span={2} versionKey={['description', 'description_translations']}>
          <LanguageToggleInput
            id='activity-description'
            label='Description'
            multiline
            rows={3}
            readOnly={locked}
            values={{
              en: editorForm.description,
              zh: editorForm.description_translations.zh,
              yue: editorForm.description_translations.yue,
            }}
            onChange={handleDescriptionChange}
          />
        </VersionField>
        {isAdmin ? (
          <>
            {importedLabel ? (
              <AdminReadOnlyValue label='Imported as' span={2}>
                {importedLabel}
              </AdminReadOnlyValue>
            ) : null}
            <VersionField
              label='Source URL'
              htmlFor='activity-source-url'
              span={2}
              versionKey='source_url'
            >
              <Input
                id='activity-source-url'
                type='url'
                value={editorForm.source_url}
                disabled={locked}
                onChange={(event) =>
                  panel.setFormState((prev) => ({
                    ...prev,
                    source_url: event.target.value,
                  }))
                }
                placeholder='https://'
              />
            </VersionField>
            <VersionField
              label='Source note'
              htmlFor='activity-source-note'
              span={2}
              versionKey='source_note'
            >
              <Textarea
                id='activity-source-note'
                rows={2}
                value={editorForm.source_note}
                disabled={locked}
                onChange={(event) =>
                  panel.setFormState((prev) => ({
                    ...prev,
                    source_note: event.target.value,
                  }))
                }
              />
            </VersionField>
          </>
        ) : null}
        <VersionField
          label='Age Min'
          htmlFor='activity-age-min'
          required
          versionKey='age_range'
          error={showAgeMinError ? ageMinError : undefined}
        >
          <Input
            id='activity-age-min'
            type='number'
            min='0'
            value={editorForm.age_min}
            disabled={locked}
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
        </VersionField>
        <VersionField
          label='Age Max'
          htmlFor='activity-age-max'
          required
          versionKey='age_range'
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
            value={editorForm.age_max}
            disabled={locked}
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
        </VersionField>
      </AdminFieldGrid>
      </div>
      </VersionFields>
    </AdminEditorPanel>
  );

  return (
    <WorkspaceScopeGate orgId={scopedOrgId} isAdmin={isAdmin} noun='activities'>
      <div className='space-y-4'>
        <h2 className='sr-only'>{PAGE_NAME}</h2>
        <OrganizationWorkspaceTitle mode={mode} orgId={scopedOrgId} />
        <ResourceTableShell
        ariaLabel={PAGE_NAME}
        rows={panel.items}
        getLabel={(item) => item.name || 'Activity'}
        middleColumnCount={3}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel='No activities yet.'
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New activity'
        onToggleDraft={panel.collapse}
        detail={detail}
        actions={
          panel.canCreate ? (
            <AdminCreateButton
              label='New activity'
              active={panel.isDraftOpen}
              onClick={panel.openDraft}
            />
          ) : null
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
              <span className='inline-flex items-center'>
                <AdminTableName>{item.name}</AdminTableName>
                <HistoricalRowMark
                  active={versionView.isHistorical && item.id === panel.editingId}
                  version={versionView.selectedVersion}
                />
              </span>
              <AdminDataTableCellMeta until='secondary' label='Category'>
                {getCategoryPath(item.category_id)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary'>
                <AdminTableNumber>
                  {formatAdminTableRange(item.age_min, item.age_max)}
                </AdminTableNumber>
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {getCategoryPath(item.category_id)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <AdminTableNumber>
                {formatAdminTableRange(item.age_min, item.age_max)}
              </AdminTableNumber>
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
