'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import currencyCodes from 'currency-codes';

import { useActivitiesByMode } from '../../hooks/use-activities-by-mode';
import { useEditDeepLink } from '../../hooks/use-edit-deep-link';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useLocationsByMode } from '../../hooks/use-locations-by-mode';
import { useResourcePanel } from '../../hooks/use-resource-panel';
import {
  formatPriceAmount,
  parseOptionalNumber,
} from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/resource-api';
import type { ActivityPricing } from '../../types/admin';
import { PricingFormCard } from './pricing/pricing-form-card';
import { PricingTableCard } from './pricing/pricing-table-card';
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

export function PricingPanel({ mode }: PricingPanelProps) {
  const panel = useResourcePanel<ActivityPricing, PricingFormState>(
    'pricing',
    mode,
    emptyForm,
    itemToForm
  );
  const { editingId, formState, setFormState } = panel;
  useEditDeepLink(panel.items, editingId, panel.startEdit);

  const { items: activities } = useActivitiesByMode(mode, { limit: 200 });
  const { items: locations } = useLocationsByMode(mode, { limit: 200 });

  // Search state
  const [searchQuery, setSearchQuery] = useState('');

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

  useEffect(() => {
    if (editingId) {
      return;
    }
    const defaultActivityId =
      activities.length === 1 ? activities[0]?.id ?? '' : '';
    const defaultLocationId =
      locations.length === 1 ? locations[0]?.id ?? '' : '';
    const shouldSetActivityDefault =
      Boolean(defaultActivityId) && !formState.activity_id;
    const shouldSetLocationDefault =
      Boolean(defaultLocationId) && !formState.location_id;
    if (!shouldSetActivityDefault && !shouldSetLocationDefault) {
      return;
    }
    setFormState((prev) => {
      const nextActivityId = prev.activity_id || defaultActivityId;
      const nextLocationId = prev.location_id || defaultLocationId;
      if (
        nextActivityId === prev.activity_id &&
        nextLocationId === prev.location_id
      ) {
        return prev;
      }
      return {
        ...prev,
        activity_id: nextActivityId,
        location_id: nextLocationId,
      };
    });
  }, [
    activities,
    locations,
    editingId,
    formState.activity_id,
    formState.location_id,
    setFormState,
  ]);

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
      const name =
        display?.of(defaultCurrencyCode) ?? defaultCurrencyCode;
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

  function getCurrencyDisplay(value?: string | null): string {
    return normalizeCurrencyCode(value);
  }

  function getCurrencySearchText(value?: string | null): string {
    const normalized = normalizeCurrencyCode(value);
    const name = currencyNameByCode.get(normalized);
    return name ? `${name} ${normalized}` : normalized;
  }

  const isFreeType = panel.formState.pricing_type === 'free';
  const showSessionsField = panel.formState.pricing_type === 'per_sessions';
  const showFreeTrialToggle = showSessionsField;

  const validate = () => {
    if (!panel.formState.activity_id || !panel.formState.location_id) {
      return 'Activity and location are required.';
    }
    if (!isFreeType) {
      if (!panel.formState.amount.trim()) {
        return 'Amount is required.';
      }
      const amountValue = Number(panel.formState.amount);
      if (!Number.isFinite(amountValue)) {
        return 'Amount must be numeric.';
      }
      if (amountValue <= 0) {
        return 'Amount must be greater than 0.';
      }
    }
    if (panel.formState.pricing_type === 'per_sessions') {
      const sessionsCount = parseOptionalNumber(
        panel.formState.sessions_count
      );
      if (sessionsCount === null || sessionsCount <= 0) {
        return 'Classes per term is required for per-term pricing.';
      }
    }
    return null;
  };

  const locationError = panel.formState.location_id
    ? ''
    : 'Select a location.';
  const activityError = panel.formState.activity_id
    ? ''
    : 'Select an activity.';

  const amountError = useMemo(() => {
    if (isFreeType) {
      return '';
    }
    const trimmed = panel.formState.amount.trim();
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
  }, [isFreeType, panel.formState.amount]);

  const sessionsError = useMemo(() => {
    if (!showSessionsField) {
      return '';
    }
    const trimmed = panel.formState.sessions_count.trim();
    if (!trimmed) {
      return 'Enter classes per term.';
    }
    const parsed = parseOptionalNumber(panel.formState.sessions_count);
    if (parsed === null || parsed <= 0) {
      return 'Classes per term must be greater than 0.';
    }
    return '';
  }, [panel.formState.sessions_count, showSessionsField]);

  const formToPayload = (form: PricingFormState) => {
    const isFree = form.pricing_type === 'free';
    const isPerTerm = form.pricing_type === 'per_sessions';
    return {
      activity_id: form.activity_id,
      location_id: form.location_id,
      pricing_type: form.pricing_type,
      amount: isFree ? '0' : form.amount.trim(),
      currency: isFree
        ? defaultCurrencyCode
        : normalizeCurrencyCode(form.currency),
      sessions_count: isPerTerm
        ? parseOptionalNumber(form.sessions_count)
        : null,
      free_trial_class_offered: isPerTerm
        ? form.free_trial_class_offered
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

  const columns = useMemo(
    () => [
      {
        key: 'location',
        header: 'Location',
        primary: true,
        render: (item: ActivityPricing) => (
          <span className='font-medium'>
            {getLocationName(item.location_id)}
          </span>
        ),
      },
      {
        key: 'activity',
        header: 'Activity',
        secondary: true,
        render: (item: ActivityPricing) => (
          <span className='text-slate-600'>
            {getActivityName(item.activity_id)}
          </span>
        ),
      },
      {
        key: 'type',
        header: 'Type',
        render: (item: ActivityPricing) => (
          <span className='text-slate-600'>
            {getPricingTypeLabel(item.pricing_type)}
          </span>
        ),
      },
      {
        key: 'amount',
        header: 'Amount',
        render: (item: ActivityPricing) =>
          item.pricing_type === 'free' ? (
            <span className='text-slate-600'>-</span>
          ) : (
            <span className='text-slate-600'>
              {getCurrencyDisplay(item.currency)}{' '}
              {formatPriceAmount(item.amount)}
            </span>
          ),
      },
    ],
    [getActivityName, getLocationName]
  );

  // Filter items based on search query
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
  const showSessionsError = shouldShowError(
    'sessions_count',
    sessionsError
  );

  return (
    <div className='space-y-6'>
      <PricingFormCard
        error={panel.error}
        formState={panel.formState}
        locations={locations}
        activities={activities}
        currencyOptions={currencyOptions}
        pricingOptions={pricingOptions}
        requiredIndicator={requiredIndicator}
        errorInputClassName={errorInputClassName}
        isFreeType={isFreeType}
        showSessionsField={showSessionsField}
        showFreeTrialToggle={showFreeTrialToggle}
        showLocationError={showLocationError}
        showActivityError={showActivityError}
        showAmountError={showAmountError}
        showSessionsError={showSessionsError}
        locationError={locationError}
        activityError={activityError}
        amountError={amountError}
        sessionsError={sessionsError}
        isSaving={panel.isSaving}
        editingId={panel.editingId}
        onLocationChange={(value) => {
          markTouched('location_id');
          panel.setFormState((prev) => ({
            ...prev,
            location_id: value,
          }));
        }}
        onActivityChange={(value) => {
          markTouched('activity_id');
          panel.setFormState((prev) => ({
            ...prev,
            activity_id: value,
          }));
        }}
        onPricingTypeChange={(value) =>
          panel.setFormState((prev) => ({
            ...prev,
            pricing_type: value,
            sessions_count: value === 'per_sessions' ? prev.sessions_count : '',
            free_trial_class_offered:
              value === 'per_sessions' ? prev.free_trial_class_offered : false,
            amount: value === 'free' ? '' : prev.amount,
            currency: value === 'free' ? defaultCurrencyCode : prev.currency,
          }))
        }
        onSessionsChange={(value) => {
          markTouched('sessions_count');
          panel.setFormState((prev) => ({
            ...prev,
            sessions_count: value,
          }));
        }}
        onFreeTrialToggle={(value) =>
          panel.setFormState((prev) => ({
            ...prev,
            free_trial_class_offered: value,
          }))
        }
        onCurrencyChange={(value) =>
          panel.setFormState((prev) => ({
            ...prev,
            currency: normalizeCurrencyCode(value),
          }))
        }
        onAmountChange={(value) => {
          markTouched('amount');
          panel.setFormState((prev) => ({
            ...prev,
            amount: value,
          }));
        }}
        onSubmit={handleSubmit}
        onCancel={panel.resetForm}
      />

      <PricingTableCard
        isLoading={panel.isLoading}
        hasItems={panel.items.length > 0}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        columns={columns}
        data={filteredItems}
        onEdit={(item) => panel.startEdit(item)}
        onDelete={(item) =>
          panel.handleDelete({
            ...item,
            name: getActivityName(item.activity_id),
          })
        }
        nextCursor={panel.nextCursor}
        onLoadMore={panel.loadMore}
      />
      {panel.confirmDialog}
    </div>
  );
}
