import type { ActivityPricing } from '../../../types/admin';

export interface PricingFormState {
  activity_id: string;
  location_id: string;
  pricing_type: string;
  amount: string;
  currency: string;
  sessions_count: string;
  free_trial_class_offered: boolean;
}

export interface CurrencyOption {
  code: string;
  name: string;
  label: string;
}

export const defaultCurrencyCode = 'HKD';

export const emptyForm: PricingFormState = {
  activity_id: '',
  location_id: '',
  pricing_type: 'per_class',
  amount: '',
  currency: defaultCurrencyCode,
  sessions_count: '',
  free_trial_class_offered: false,
};

export const pricingOptions = [
  { value: 'per_class', label: 'Per class' },
  { value: 'per_sessions', label: 'Per term' },
  { value: 'per_hour', label: 'Hourly' },
  { value: 'per_day', label: 'Daily' },
  { value: 'free', label: 'Free' },
  { value: 'per_month', label: 'Monthly' },
  { value: 'per_year', label: 'Yearly' },
];

const pricingTypeLabelByValue = new Map(
  pricingOptions.map((option) => [option.value, option.label])
);

export function getPricingTypeLabel(value: string): string {
  return pricingTypeLabelByValue.get(value) ?? value;
}

export function normalizeCurrencyCode(value?: string | null): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    return defaultCurrencyCode;
  }
  return trimmed.toUpperCase();
}

export function itemToForm(item: ActivityPricing): PricingFormState {
  return {
    activity_id: item.activity_id ?? '',
    location_id: item.location_id ?? '',
    pricing_type: item.pricing_type,
    amount:
      item.pricing_type === 'free'
        ? ''
        : item.amount != null
          ? String(item.amount)
          : '',
    currency: normalizeCurrencyCode(item.currency),
    sessions_count: item.sessions_count ? `${item.sessions_count}` : '',
    free_trial_class_offered: Boolean(item.free_trial_class_offered),
  };
}
