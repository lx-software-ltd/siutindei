'use client';

import { useCallback, useMemo, useState } from 'react';

import currencyCodes from 'currency-codes';

import { useActivitiesByMode } from '../../hooks/use-activities-by-mode';
import { useExhaustPages } from '../../hooks/use-exhaust-pages';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useLocationsByMode } from '../../hooks/use-locations-by-mode';
import { useOrganizationScope } from '../../hooks/use-organization-scope';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import {
  formatPriceAmount,
  parseOptionalNumber,
} from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/resource-api';
import type { ActivityPricing } from '../../types/admin';
import { StatusBanner } from '../status-banner';
import { OrganizationWorkspaceTitle } from '../admin/organization-workspace-title';
import { WorkspaceScopeGate } from '../admin/workspace-empty';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid, formErrorClassName } from '../ui/admin-field-grid';
import { AdminFilterBar, AdminFilterField } from '../ui/admin-filter-bar';
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
  type CurrencyOption,
  type PricingFormState,
} from './pricing/pricing-types';

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

  const { items: activities } = useActivitiesByMode(mode, {
    limit: 200,
    orgId: scopedOrgId,
  });
  const { items: locations } = useLocationsByMode(mode, {
    limit: 200,
    orgId: scopedOrgId,
  });

  const [searchQuery, setSearchQuery] = useState('');
  useExhaustPages(Boolean(searchQuery.trim()), {
    hasMore: panel.hasMore,
    isLoading: panel.isLoading,
    isLoadingMore: panel.isLoadingMore,
    error: panel.listError,
    loadMore: panel.loadMore,
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

  const currencyOptions = useMemo<CurrencyOption[]>(() => {
    const display =
      typeof Intl !== 'undefined' &&
      typeof Intl.DisplayNames === 'function'
        ? new Intl.DisplayNames(['en'], { type: 'currency' })
        : null;
    const optionsMap = new Map<string, CurrencyOption>();
    for (const record of currencyCodes.data) {
      const code = record.code?.toUpperCase();
      if (!code) {
        continue;
      }
      const name = display?.of(code) ?? record.currency ?? code;
      optionsMap.set(code, {
        code,
        name,
        label: `${name} (${code})`,
      });
    }
    if (!optionsMap.has(defaultCurrencyCode)) {
      const name = display?.of(defaultCurrencyCode) ?? defaultCurrencyCode;
      optionsMap.set(defaultCurrencyCode, {
        code: defaultCurrencyCode,
        name,
        label: `${name} (${defaultCurrencyCode})`,
      });
    }
    return Array.from(optionsMap.values()).sort((a, b) =>
      a.label.localeCompare(b.label)
    );
  }, []);

  const currencyNameByCode = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of currencyOptions) {
      map.set(option.code, option.name);
    }
    return map;
  }, [currencyOptions]);

  function getCurrencySearchText(value?: string | null): string {
    const normalized = normalizeCurrencyCode(value);
    const name = currencyNameByCode.get(normalized);
    return name ? `${name} ${normalized}` : normalized;
  }

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
    (locationId: string) =>
      locations.find((location) => location.id === locationId)?.address ??
      locationId,
    [locations]
  );

  const filteredItems = panel.items.filter((item) => {
    if (!searchQuery.trim()) {
      return true;
    }
    const query = searchQuery.toLowerCase();
    const activityName = getActivityName(item.activity_id);
    const locationName = getLocationName(item.location_id);
    const pricingTypeLabel = getPricingTypeLabel(item.pricing_type);
    const pricingTypeSearch =
      `${pricingTypeLabel} ${item.pricing_type}`.toLowerCase();
    const currencySearch = getCurrencySearchText(item.currency).toLowerCase();
    const amountSearch = String(item.amount).toLowerCase();
    const formattedAmountSearch = formatPriceAmount(item.amount).toLowerCase();
    return (
      activityName.toLowerCase().includes(query) ||
      locationName.toLowerCase().includes(query) ||
      pricingTypeSearch.includes(query) ||
      amountSearch.includes(query) ||
      formattedAmountSearch.includes(query) ||
      currencySearch.includes(query)
    );
  });

  const showLocationError = shouldShowError('location_id', locationError);
  const showActivityError = shouldShowError('activity_id', activityError);
  const showAmountError = shouldShowError('amount', amountError);
  const showSessionsError = shouldShowError('sessions_count', sessionsError);

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
        <AdminField
          label='Location'
          htmlFor='pricing-location'
          required
          error={showLocationError ? locationError : undefined}
        >
          <Select
            id='pricing-location'
            value={formState.location_id}
            onChange={(event) => {
              markTouched('location_id');
              panel.setFormState((prev) => ({
                ...prev,
                location_id: event.target.value,
              }));
            }}
            className={showLocationError ? errorInputClassName : ''}
            aria-invalid={showLocationError || undefined}
          >
            <option value=''>Select location</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.address || location.area_id}
              </option>
            ))}
          </Select>
        </AdminField>
        <AdminField
          label='Activity'
          htmlFor='pricing-activity'
          required
          error={showActivityError ? activityError : undefined}
        >
          <Select
            id='pricing-activity'
            value={formState.activity_id}
            onChange={(event) => {
              markTouched('activity_id');
              panel.setFormState((prev) => ({
                ...prev,
                activity_id: event.target.value,
              }));
            }}
            className={showActivityError ? errorInputClassName : ''}
            aria-invalid={showActivityError || undefined}
          >
            <option value=''>Select activity</option>
            {activities.map((activity) => (
              <option key={activity.id} value={activity.id}>
                {activity.name}
              </option>
            ))}
          </Select>
        </AdminField>
        <AdminField
          label='Pricing Type'
          htmlFor='pricing-type'
          span={showSessionsField ? 1 : 2}
        >
          <Select
            id='pricing-type'
            value={formState.pricing_type}
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
        </AdminField>
        {showSessionsField ? (
          <AdminField
            label='Classes per term'
            htmlFor='pricing-sessions'
            required
            error={showSessionsError ? sessionsError : undefined}
          >
            <Input
              id='pricing-sessions'
              type='number'
              min='1'
              value={formState.sessions_count}
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
          </AdminField>
        ) : null}
        {showFreeTrialToggle ? (
          <AdminField span={2}>
            <label className='flex items-center gap-2 text-sm'>
              <input
                id='pricing-free-trial'
                type='checkbox'
                checked={formState.free_trial_class_offered}
                onChange={(event) =>
                  panel.setFormState((prev) => ({
                    ...prev,
                    free_trial_class_offered: event.target.checked,
                  }))
                }
                className='h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500'
              />
              <span>Free trial class offered</span>
            </label>
          </AdminField>
        ) : null}
        <AdminField label='Currency' htmlFor='pricing-currency'>
          <Select
            id='pricing-currency'
            value={formState.currency}
            disabled={isFreeType}
            onChange={(event) =>
              panel.setFormState((prev) => ({
                ...prev,
                currency: normalizeCurrencyCode(event.target.value),
              }))
            }
          >
            {currencyOptions.map((option) => (
              <option key={option.code} value={option.code}>
                {option.label}
              </option>
            ))}
          </Select>
        </AdminField>
        <AdminField
          label='Amount'
          htmlFor='pricing-amount'
          required={!isFreeType}
          error={showAmountError ? amountError : undefined}
        >
          <Input
            id='pricing-amount'
            type='number'
            step='0.01'
            value={formState.amount}
            disabled={isFreeType}
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
        </AdminField>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <WorkspaceScopeGate orgId={scopedOrgId} isAdmin={isAdmin} noun='pricing'>
      <div className='space-y-4'>
        <OrganizationWorkspaceTitle mode={mode} orgId={scopedOrgId} />
        <ResourceTableShell
        ariaLabel='Pricing'
        rows={filteredItems}
        getLabel={(item) => getLocationName(item.location_id)}
        middleColumnCount={4}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel={
          searchQuery.trim()
            ? 'No pricing entries match your search.'
            : 'No pricing entries yet.'
        }
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New pricing'
        onToggleDraft={panel.collapse}
        detail={detail}
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New pricing'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          >
            <AdminFilterField>
              <Input
                id='pricing-search'
                placeholder='Search pricing...'
                aria-label='Search pricing'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
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
              {getLocationName(item.location_id)}
              <AdminDataTableCellMeta until='secondary'>
                {pricingAmountLabel(item)}
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
