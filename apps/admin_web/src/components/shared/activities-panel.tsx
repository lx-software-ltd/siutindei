'use client';

import { useEffect, useMemo, useState } from 'react';

import { useActivityCategories } from '../../hooks/use-activity-categories';
import { useEditDeepLink } from '../../hooks/use-edit-deep-link';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationsByMode } from '../../hooks/use-organizations-by-mode';
import { useResourcePanel } from '../../hooks/use-resource-panel';
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
import { CascadingCategorySelect } from '../ui/cascading-category-select';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { DataTable } from '../ui/data-table';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { LanguageToggleInput } from '../ui/language-toggle-input';
import { SearchInput } from '../ui/search-input';
import { Select } from '../ui/select';
import { StatusBanner } from '../status-banner';

interface ActivityFormState {
  org_id: string;
  category_id: string;
  name: string;
  description: string;
  name_translations: Record<TranslationLanguageCode, string>;
  description_translations: Record<TranslationLanguageCode, string>;
  age_min: string;
  age_max: string;
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
  };
}

interface ActivitiesPanelProps {
  mode: ApiMode;
}

export function ActivitiesPanel({ mode }: ActivitiesPanelProps) {
  const isAdmin = mode === 'admin';
  const panel = useResourcePanel<Activity, ActivityFormState>(
    'activities',
    mode,
    emptyForm,
    itemToForm
  );
  useEditDeepLink(panel.items, panel.editingId, panel.startEdit);

  const { tree: categoryTree } = useActivityCategories();

  const { items: organizations } = useOrganizationsByMode(mode, { limit: 200 });

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

  // Search state
  const [searchQuery, setSearchQuery] = useState('');

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['org_id', 'name', 'category_id', 'age_min', 'age_max'],
    formKey
  );
  const requiredIndicator = validation.requiredIndicator;
  const errorInputClassName =
    'border-red-500 focus:border-red-500 focus:ring-red-500';
  const { markTouched } = validation;
  const shouldShowError = (field: string, message: string) =>
    validation.shouldShowError(field, Boolean(message));

  // For managers with a single org, auto-select and disable the dropdown
  const isSingleOrgManager = !isAdmin && organizations.length === 1;

  const { setFormState } = panel;

  useEffect(() => {
    if (isAdmin || organizations.length !== 1) {
      return;
    }
    const orgId = organizations[0].id;
    setFormState((prev) =>
      prev.org_id === orgId ? prev : { ...prev, org_id: orgId }
    );
  }, [isAdmin, organizations, setFormState]);

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
    if (ageMin === null || ageMax === null) {
      return 'Age range must be numeric.';
    }
    if (ageMin >= ageMax) {
      return 'Age min must be less than age max.';
    }
    return null;
  };

  const orgError = panel.formState.org_id ? '' : 'Select an organization.';

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
  });

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

  const columns = useMemo(() => {
    const getOrgName = (orgId?: string) => {
      if (!orgId) {
        return '';
      }
      const match = organizations.find((org) => org.id === orgId);
      return match?.name ?? orgId;
    };

    const getCategoryLabel = (categoryId?: string) =>
      (categoryId ? categoryPathById.get(categoryId) : undefined) ?? '—';

    return [
      {
        key: 'name',
        header: isAdmin ? 'Organization / Activity' : 'Name',
        primary: true,
        render: (item: Activity) =>
          isAdmin
            ? `${getOrgName(item.org_id)} - ${item.name}`
            : item.name,
      },
      {
        key: 'category',
        header: 'Category',
        secondary: true,
        render: (item: Activity) => getCategoryLabel(item.category_id),
      },
      {
        key: 'age-range',
        header: 'Age Range',
        render: (item: Activity) => `${item.age_min} - ${item.age_max}`,
      },
    ];
  }, [categoryPathById, isAdmin, organizations]);

  // Filter items based on search query
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
    const orgName =
      organizations
        .find((org) => org.id === item.org_id)
        ?.name?.toLowerCase() || '';
    const categoryPath = getCategoryPath(item.category_id).toLowerCase();
    return (
      item.name?.toLowerCase().includes(query) ||
      item.description?.toLowerCase().includes(query) ||
      nameTranslations.includes(query) ||
      descriptionTranslations.includes(query) ||
      orgName.includes(query) ||
      categoryPath.includes(query)
    );
  });

  const showOrgError = shouldShowError('org_id', orgError);
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

  return (
    <div className='space-y-6'>
      <Card title='Activities' description='Manage activity entries.'>
        {panel.error && (
          <div className='mb-4'>
            <StatusBanner variant='error' title='Error'>
              {panel.error}
            </StatusBanner>
          </div>
        )}
        <div className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-1'>
            <Label htmlFor='activity-org'>
              Organization{' '}
              <span className='ml-1'>{requiredIndicator}</span>
            </Label>
            <Select
              id='activity-org'
              value={panel.formState.org_id}
              onChange={(e) => {
                markTouched('org_id');
                panel.setFormState((prev) => ({
                  ...prev,
                  org_id: e.target.value,
                }));
              }}
              disabled={isSingleOrgManager}
              className={showOrgError ? errorInputClassName : ''}
              aria-invalid={showOrgError || undefined}
            >
              <option value=''>Select organization</option>
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </Select>
            {showOrgError ? (
              <p className='text-xs text-red-600'>{orgError}</p>
            ) : null}
          </div>
          <div className='space-y-1'>
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
            {showNameError ? (
              <p className='text-xs text-red-600'>{nameError}</p>
            ) : null}
          </div>
          <div className='md:col-span-2'>
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
          </div>
          <div className='md:col-span-2'>
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
          </div>
          <div className='space-y-1'>
            <Label htmlFor='activity-age-min'>
              Age Min{' '}
              <span className='ml-1'>{requiredIndicator}</span>
            </Label>
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
            {showAgeMinError ? (
              <p className='text-xs text-red-600'>{ageMinError}</p>
            ) : null}
          </div>
          <div className='space-y-1'>
            <Label htmlFor='activity-age-max'>
              Age Max{' '}
              <span className='ml-1'>{requiredIndicator}</span>
            </Label>
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
            {showAgeMaxError ? (
              <p className='text-xs text-red-600'>{ageMaxError}</p>
            ) : showAgeRangeError ? (
              <p className='text-xs text-red-600'>{ageRangeError}</p>
            ) : null}
          </div>
        </div>
        <div className='mt-4 flex flex-wrap gap-3'>
          <Button
            type='button'
            onClick={handleSubmit}
            disabled={panel.isSaving}
          >
            {panel.editingId ? 'Update Activity' : 'Add Activity'}
          </Button>
          {panel.editingId && (
            <Button
              type='button'
              variant='secondary'
              onClick={panel.resetForm}
              disabled={panel.isSaving}
            >
              Cancel
            </Button>
          )}
        </div>
      </Card>

      <Card
        title='Existing Activities'
        description='Select an activity to edit or delete.'
      >
        {panel.isLoading && panel.items.length === 0 ? (
          <p className='text-sm text-slate-600'>Loading activities...</p>
        ) : panel.items.length === 0 ? (
          <p className='text-sm text-slate-600'>No activities yet.</p>
        ) : (
          <div className='space-y-4'>
            <div className='max-w-full sm:max-w-sm'>
              <SearchInput
                placeholder='Search activities...'
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <DataTable
              columns={columns}
              data={filteredItems}
              keyExtractor={(item) => item.id}
              onEdit={(item) => panel.startEdit(item)}
              onDelete={(item) => panel.handleDelete(item)}
              nextCursor={panel.nextCursor}
              onLoadMore={panel.loadMore}
              isLoading={panel.isLoading}
              emptyMessage={
                searchQuery.trim()
                  ? 'No activities match your search.'
                  : 'No activities yet.'
              }
            />
          </div>
        )}
      </Card>
      {panel.confirmDialog}
    </div>
  );
}
