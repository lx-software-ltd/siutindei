'use client';

import { useMemo } from 'react';

import { useFormValidation } from '../../hooks/use-form-validation';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import {
  buildTranslationsPayload,
  emptyTranslations,
  extractTranslations,
  type LanguageCode,
  type TranslationLanguageCode,
} from '../../lib/translations';
import type { FeedbackLabel } from '../../types/admin';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminFilterBar } from '../ui/admin-filter-bar';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { LanguageToggleInput } from '../ui/language-toggle-input';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { StatusBanner } from '../status-banner';

interface FeedbackLabelFormState {
  name: string;
  name_translations: Record<TranslationLanguageCode, string>;
  display_order: string;
}

const emptyForm: FeedbackLabelFormState = {
  name: '',
  name_translations: emptyTranslations(),
  display_order: '0',
};

function itemToForm(item: FeedbackLabel): FeedbackLabelFormState {
  return {
    name: item.name ?? '',
    name_translations: extractTranslations(item.name_translations),
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

function translationSummary(item: FeedbackLabel): string {
  const translations = Object.entries(item.name_translations ?? {})
    .map(([lang, value]) => `${lang}: ${value}`)
    .join(', ');
  return translations || '—';
}

export function FeedbackLabelsPanel() {
  const panel = useResourceEditor<FeedbackLabel, FeedbackLabelFormState>({
    resource: 'feedback-labels',
    mode: 'admin',
    emptyForm,
    itemToForm,
    paramName: 'feedback-label',
    noun: 'feedback label',
  });

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['name', 'display_order'],
    formKey
  );

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
    : 'Enter a label name.';
  const displayOrderError = useMemo(() => {
    const order = parseDisplayOrder(panel.formState.display_order);
    if (order === null || order < 0) {
      return 'Display order must be a whole number.';
    }
    return '';
  }, [panel.formState.display_order]);

  const handleNameChange = (language: LanguageCode, value: string) => {
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

  const formToPayload = (form: FeedbackLabelFormState) => ({
    name: form.name.trim(),
    name_translations: buildTranslationsPayload(form.name_translations),
    display_order: parseDisplayOrder(form.display_order),
  });

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

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
            id='label-name'
            label='Label Name'
            required
            values={{
              en: panel.formState.name,
              zh: panel.formState.name_translations.zh,
              yue: panel.formState.name_translations.yue,
            }}
            onChange={handleNameChange}
            hasError={showNameError}
            inputClassName={validation.errorClassName(
              'name',
              Boolean(nameError)
            )}
          />
          {showNameError ? (
            <p className='text-xs text-red-600'>{nameError}</p>
          ) : null}
        </div>
        <div className='space-y-1'>
          <Label htmlFor='display-order'>Display Order</Label>
          <Input
            id='display-order'
            type='number'
            value={panel.formState.display_order}
            onChange={(e) => {
              validation.markTouched('display_order');
              panel.setFormState((prev) => ({
                ...prev,
                display_order: e.target.value,
              }));
            }}
            onBlur={() => validation.markTouched('display_order')}
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
        ariaLabel='Feedback labels'
        rows={panel.items}
        getLabel={(item) => item.name || 'Label'}
        middleColumnCount={3}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel='No feedback labels found.'
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New feedback label'
        onToggleDraft={panel.collapse}
        detail={detail}
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New feedback label'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          />
        }
        head={
          <>
            <AdminDataTableHeadCell>Label</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Order
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Translations
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              {item.name}
              <AdminDataTableCellMeta until='tertiary'>
                {translationSummary(item)}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.display_order ?? 0}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {translationSummary(item)}
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) =>
          deleteRowActions(() => panel.handleDelete(item))
        }
      />
      {panel.confirmDialog}
    </>
  );
}
