'use client';

import { useCallback, useMemo } from 'react';

import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationScope } from '../../hooks/use-organization-scope';
import { useResourceByMode } from '../../hooks/use-resource-by-mode';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { adminCurrencyOptions } from '../../lib/admin-currencies';
import { formatAdminPageName } from '../../lib/admin-page-name';
import { locationDisplayName } from '../../lib/location-label';
import type { ApiMode } from '../../lib/api-client-admin';
import {
  formatPriceAmount,
  parseOptionalNumber,
} from '../../lib/number-parsers';
import type { Activity, ActivityPricing, Location } from '../../types/admin';
import { pricingFormFromSnapshot } from '../admin/catalog-version-snapshot';
import { OrganizationWorkspaceTitle } from '../admin/organization-workspace-title';
import {
  HistoricalRowMark,
  useCatalogVersion,
  VersionField,
} from '../admin/version-history';
import { WorkspaceScopeGate } from '../admin/workspace-empty';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { formErrorClassName } from '../ui/admin-field-grid';
import { AdminTableName } from '../ui/admin-table-value';
import { CatalogInlineEditor } from './catalog-inline-editor';
import { Input } from '../ui/input';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { Select } from '../ui/select';
import {
  defaultCurrencyCode,
  emptyForm,
  getPricingTypeLabel,
  itemToForm,
  normalizeCurrencyCode,
  pricingOptions,
  type PricingFormState,
} from './pricing/pricing-types';

const PAGE_NAME = formatAdminPageName('Pricing');

interface PricingPanelProps {
  mode: ApiMode;
}

function pricingAmountLabel(item: ActivityPricing): string {
  if (item.pricing_type === 'free') {
    return '-';
  }
  return `${normalizeCurrencyCode(item.currency)} ${formatPriceAmount(item.amount)}`;
}

function applyCreateDefaults(
  form: PricingFormState,
  editingId: string | null,
  singleActivityId: string,
  singleLocationId: string
): PricingFormState {
  if (editingId) {
    return form;
  }
  const activityId = form.activity_id || singleActivityId;
  const locationId = form.location_id || singleLocationId;
  if (activityId === form.activity_id && locationId === form.location_id) {
    return form;
  }
  return {
    ...form,
    activity_id: activityId,
    location_id: locationId,
  };
}

export function PricingPanel({ mode }: PricingPanelProps) {
  const isAdmin = mode === 'admin';
  const scope = useOrganizationScope();
  const scopedOrgId = scope.orgId;
  const panel = useResourceEditor<ActivityPricing, PricingFormState>({
    resource: 'pricing',
    mode,
    emptyForm,
    itemToForm,
    paramName: 'pricing',
    legacyParam: 'edit',
    listFilters: scopedOrgId ? { org_id: scopedOrgId } : {},
    enabled: Boolean(scopedOrgId),
    noun: 'pricing',
  });

  const { items: activities } = useResourceByMode<Activity>('activities', mode, {
    limit: 200,
    orgId: scopedOrgId,
  });
  const { items: locations } = useResourceByMode<Location>('locations', mode, {
    limit: 200,
    orgId: scopedOrgId,
  });

  const singleActivityId =
    activities.length === 1 ? (activities[0]?.id ?? '') : '';
  const singleLocationId =
    locations.length === 1 ? (locations[0]?.id ?? '') : '';
  const formState = useMemo(
    () =>
      applyCreateDefaults(
        panel.formState,
        panel.editingId,
        singleActivityId,
        singleLocationId
      ),
    [panel.editingId, panel.formState, singleActivityId, singleLocationId]
  );

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['location_id', 'activity_id', 'sessions_count', 'amount'],
    formKey
  );
  const errorInputClassName = formErrorClassName;
  const { markTouched } = validation;
  const shouldShowError = (field: string, message: string) =>
    validation.shouldShowError(field, Boolean(message));

  const isFreeType = formState.pricing_type === 'free';
  const showSessionsField = formState.pricing_type === 'per_sessions';
  const showFreeTrialToggle = showSessionsField;

  const validate = () => {
    if (!formState.activity_id || !formState.location_id) {
      return 'Activity and location are required.';
    }
    if (!isFreeType) {
      if (!formState.amount.trim()) {
        return 'Amount is required.';
      }
      const amountValue = Number(formState.amount);
      if (!Number.isFinite(amountValue)) {
        return 'Amount must be numeric.';
      }
      if (amountValue <= 0) {
        return 'Amount must be greater than 0.';
      }
    }
    if (formState.pricing_type === 'per_sessions') {
      const sessionsCount = parseOptionalNumber(formState.sessions_count);
      if (sessionsCount === null || sessionsCount <= 0) {
        return 'Classes per term is required for per-term pricing.';
      }
    }
    return null;
  };

  const locationError = formState.location_id ? '' : 'Select a location.';
  const activityError = formState.activity_id ? '' : 'Select an activity.';

  const amountError = useMemo(() => {
    if (isFreeType) {
      return '';
    }
    const trimmed = formState.amount.trim();
    if (!trimmed) {
      return 'Enter an amount.';
    }
    const amountValue = Number(trimmed);
    if (!Number.isFinite(amountValue)) {
      return 'Amount must be numeric.';
    }
    if (amountValue <= 0) {
      return 'Amount must be greater than 0.';
    }
    return '';
  }, [formState.amount, isFreeType]);

  const sessionsError = useMemo(() => {
    if (!showSessionsField) {
      return '';
    }
    const trimmed = formState.sessions_count.trim();
    if (!trimmed) {
      return 'Enter classes per term.';
    }
    const parsed = parseOptionalNumber(formState.sessions_count);
    if (parsed === null || parsed <= 0) {
      return 'Classes per term must be greater than 0.';
    }
    return '';
  }, [formState.sessions_count, showSessionsField]);

  const formToPayload = (form: PricingFormState) => {
    const resolved = applyCreateDefaults(
      form,
      panel.editingId,
      singleActivityId,
      singleLocationId
    );
    const isFree = resolved.pricing_type === 'free';
    const isPerTerm = resolved.pricing_type === 'per_sessions';
    return {
      activity_id: resolved.activity_id,
      location_id: resolved.location_id,
      pricing_type: resolved.pricing_type,
      amount: isFree ? '0' : resolved.amount.trim(),
      currency: isFree
        ? defaultCurrencyCode
        : normalizeCurrencyCode(resolved.currency),
      sessions_count: isPerTerm
        ? parseOptionalNumber(resolved.sessions_count)
        : null,
      free_trial_class_offered: isPerTerm
        ? resolved.free_trial_class_offered
        : false,
    };
  };

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

  const getActivityName = useCallback(
    (activityId: string) =>
      activities.find((activity) => activity.id === activityId)?.name ??
      activityId,
    [activities]
  );

  const getLocationName = useCallback(
    (locationId: string) => {
      const location = locations.find((item) => item.id === locationId);
      if (!location) {
        return locationId;
      }
      return locationDisplayName(location, locationId);
    },
    [locations]
  );

  const showLocationError = shouldShowError('location_id', locationError);
  const showActivityError = shouldShowError('activity_id', activityError);
  const showAmountError = shouldShowError('amount', amountError);
  const showSessionsError = shouldShowError('sessions_count', sessionsError);
  const versionView = useCatalogVersion({
    mode,
    entityType: 'pricing',
    entityId: panel.editingId,
    version: panel.items.find((item) => item.id === panel.editingId)?.version,
  });
  const locked = versionView.locked;
  const editorForm = versionView.snapshot
    ? pricingFormFromSnapshot(versionView.snapshot, formState)
    : formState;
  const editorIsFree = editorForm.pricing_type === 'free';
  const editorShowSessions = editorForm.pricing_type === 'per_sessions';

  const detail = (
    <CatalogInlineEditor
      idPrefix='pricing'
      view={versionView}
      editingId={panel.editingId}
      error={panel.error}
      isHistorical={versionView.isHistorical}
      onBackToLatest={versionView.backToLatest}
      editorMode={panel.editorMode}
      onSubmit={handleSubmit}
      isSaving={panel.isSaving}
      locations={locations}
      activities={activities}
      locationId={editorForm.location_id}
      activityId={editorForm.activity_id}
      locked={locked}
      showLocationError={showLocationError}
      showActivityError={showActivityError}
      locationError={locationError}
      activityError={activityError}
      errorClassName={errorInputClassName}
      onLocationChange={(value) => {
        markTouched('location_id');
        panel.setFormState((prev) => ({ ...prev, location_id: value }));
      }}
      onActivityChange={(value) => {
        markTouched('activity_id');
        panel.setFormState((prev) => ({ ...prev, activity_id: value }));
      }}
    >
        <VersionField
          label='Pricing Type'
          htmlFor='pricing-type'
          versionKey='pricing_type'
          span={editorShowSessions ? 1 : 2}
        >
          <Select
            id='pricing-type'
            value={editorForm.pricing_type}
            disabled={locked}
            onChange={(event) => {
              const value = event.target.value;
              panel.setFormState((prev) => ({
                ...prev,
                pricing_type: value,
                sessions_count:
                  value === 'per_sessions' ? prev.sessions_count : '',
                free_trial_class_offered:
                  value === 'per_sessions'
                    ? prev.free_trial_class_offered
                    : false,
                amount: value === 'free' ? '' : prev.amount,
                currency:
                  value === 'free' ? defaultCurrencyCode : prev.currency,
              }));
            }}
          >
            {pricingOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </VersionField>
        {editorShowSessions ? (
          <VersionField
            label='Classes per term'
            htmlFor='pricing-sessions'
            required
            versionKey='sessions_count'
            error={showSessionsError ? sessionsError : undefined}
          >
            <Input
              id='pricing-sessions'
              type='number'
              min='1'
              value={editorForm.sessions_count}
              disabled={locked}
              onChange={(event) => {
                markTouched('sessions_count');
                panel.setFormState((prev) => ({
                  ...prev,
                  sessions_count: event.target.value,
                }));
              }}
              className={showSessionsError ? errorInputClassName : ''}
              aria-invalid={showSessionsError || undefined}
            />
          </VersionField>
        ) : null}
        {editorShowSessions ? (
          <VersionField span={2} versionKey='free_trial_class_offered'>
            <label className='flex items-center gap-2 text-sm'>
              <input
                id='pricing-free-trial'
                type='checkbox'
                checked={editorForm.free_trial_class_offered}
                disabled={locked}
                onChange={(event) =>
                  panel.setFormState((prev) => ({
                    ...prev,
                    free_trial_class_offered: event.target.checked,
                  }))
                }
                className='h-4 w-4 rounded border-ink-900/15 text-ink-900 focus:ring-brand-700'
              />
              <span>Free trial class offered</span>
            </label>
          </VersionField>
        ) : null}
        <VersionField label='Currency' htmlFor='pricing-currency' versionKey='currency'>
          <Select
            id='pricing-currency'
            value={editorForm.currency}
            disabled={locked || editorIsFree}
            onChange={(event) =>
              panel.setFormState((prev) => ({
                ...prev,
                currency: normalizeCurrencyCode(event.target.value),
              }))
            }
          >
            {adminCurrencyOptions.map((option) => (
              <option key={option.code} value={option.code}>
                {option.label}
              </option>
            ))}
          </Select>
        </VersionField>
        <VersionField
          label='Amount'
          htmlFor='pricing-amount'
          versionKey='amount'
          required={!editorIsFree}
          error={showAmountError ? amountError : undefined}
        >
          <Input
            id='pricing-amount'
            type='number'
            step='0.01'
            value={editorForm.amount}
            disabled={locked || editorIsFree}
            onChange={(event) => {
              markTouched('amount');
              panel.setFormState((prev) => ({
                ...prev,
                amount: event.target.value,
              }));
            }}
            className={showAmountError ? errorInputClassName : ''}
            aria-invalid={showAmountError || undefined}
          />
        </VersionField>
    </CatalogInlineEditor>
  );

  return (
    <WorkspaceScopeGate orgId={scopedOrgId} isAdmin={isAdmin} noun='pricing'>
      <div className='space-y-4'>
        <h2 className='sr-only'>{PAGE_NAME}</h2>
        <OrganizationWorkspaceTitle mode={mode} orgId={scopedOrgId} />
        <ResourceTableShell
        ariaLabel={PAGE_NAME}
        rows={panel.items}
        getLabel={(item) => getLocationName(item.location_id)}
        middleColumnCount={4}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel='No pricing entries yet.'
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New pricing'
        onToggleDraft={panel.collapse}
        detail={detail}
        actions={
          panel.canCreate ? (
            <AdminCreateButton
              label='New pricing'
              active={panel.isDraftOpen}
              onClick={panel.openDraft}
            />
          ) : null
        }
        head={
          <>
            <AdminDataTableHeadCell>Location</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Activity
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Amount
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Type
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <span className='inline-flex items-center'>
                <AdminTableName>{getLocationName(item.location_id)}</AdminTableName>
                <HistoricalRowMark
                  active={versionView.isHistorical && item.id === panel.editingId}
                  version={versionView.selectedVersion}
                />
              </span>
              <AdminDataTableCellMeta until='secondary' label='Activity'>
                {getActivityName(item.activity_id)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary'>
                {pricingAmountLabel(item)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary'>
                {getPricingTypeLabel(item.pricing_type)}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {getActivityName(item.activity_id)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {pricingAmountLabel(item)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {getPricingTypeLabel(item.pricing_type)}
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) =>
          deleteRowActions(() =>
            panel.handleDelete({
              ...item,
              name: getActivityName(item.activity_id),
            })
          )
        }
      />
        {panel.confirmDialog}
      </div>
    </WorkspaceScopeGate>
  );
}
