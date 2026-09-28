'use client';

import { useCallback, useMemo, useState } from 'react';

import currencyCodes from 'currency-codes';

import { useActivitiesByMode } from '../../hooks/use-activities-by-mode';
import { useExhaustPages } from '../../hooks/use-exhaust-pages';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useLocationsByMode } from '../../hooks/use-locations-by-mode';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import {
  formatPriceAmount,
  parseOptionalNumber,
} from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/resource-api';
import type { ActivityPricing } from '../../types/admin';
import { StatusBanner } from '../status-banner';
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
  const panel = useResourceEditor<ActivityPricing, PricingFormState>({
    resource: 'pricing',
    mode,
    emptyForm,
    itemToForm,
    paramName: 'pricing',
    legacyParam: 'edit',
    noun: 'pricing',
  });

  const { items: activities } = useActivitiesByMode(mode, { limit: 200 });
  const { items: locations } = useLocationsByMode(mode, { limit: 200 });

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
  const requiredIndicator = validation.requiredIndicator;
  const errorInputClassName =
    'border-red-500 focus:border-red-500 focus:ring-red-500';
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
          <Label htmlFor='pricing-location'>
            Location <span className='ml-1'>{requiredIndicator}</span>
          </Label>
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
          {showLocationError ? (
            <p className='text-xs text-red-600'>{locationError}</p>
          ) : null}
        </div>
        <div className='space-y-1'>
          <Label htmlFor='pricing-activity'>
            Activity <span className='ml-1'>{requiredIndicator}</span>
          </Label>
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
          {showActivityError ? (
            <p className='text-xs text-red-600'>{activityError}</p>
          ) : null}
        </div>
        <div
          className={
            showSessionsField ? 'space-y-1' : 'space-y-1 sm:col-span-2'
          }
        >
          <Label htmlFor='pricing-type'>Pricing Type</Label>
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
        </div>
        {showSessionsField ? (
          <div className='space-y-1'>
            <Label htmlFor='pricing-sessions'>
              Classes per term <span className='ml-1'>{requiredIndicator}</span>
            </Label>
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
            {showSessionsError ? (
              <p className='text-xs text-red-600'>{sessionsError}</p>
            ) : null}
          </div>
        ) : null}
        {showFreeTrialToggle ? (
          <div className='sm:col-span-2'>
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
          </div>
        ) : null}
        <div className='space-y-1'>
          <Label htmlFor='pricing-currency'>Currency</Label>
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
        </div>
        <div className='space-y-1'>
          <Label htmlFor='pricing-amount'>
            Amount
            {!isFreeType ? (
              <span className='ml-1'>{requiredIndicator}</span>
            ) : null}
          </Label>
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
          {showAmountError ? (
            <p className='text-xs text-red-600'>{amountError}</p>
          ) : null}
        </div>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <>
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
    </>
  );
}
