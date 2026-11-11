import type { Locale } from '@/content/locales';
import { formatTemplate } from '@/lib/format-template';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

import { languageLabel } from './listing-facts';
import { formatMoney } from './price-format';
import { dayLabel } from './schedule-format';
import {
  placeLabelForFilters,
  type SearchDayChoice,
  type SearchFiltersState,
} from './search-params';

export interface ActiveFilterCopy {
  readonly allAgesLabel: string;
  readonly freeFilterLabel: string;
  readonly freeTrialFilterLabel: string;
  readonly weekendLabel: string;
  readonly weekdaysLabel: string;
  readonly priceUpToLabel: string;
}

export interface ActiveFilter {
  readonly id: string;
  readonly label: string;
  /** Filters without this one, or null when it cannot be removed. */
  readonly without: SearchFiltersState | null;
}

export function dayChoiceLabel(
  locale: Locale,
  day: SearchDayChoice,
  copy: Pick<ActiveFilterCopy, 'weekendLabel' | 'weekdaysLabel'>,
): string {
  if (day === 'weekend') {
    return copy.weekendLabel;
  }
  if (day === 'weekdays') {
    return copy.weekdaysLabel;
  }
  return dayLabel(locale, Number(day), 'long');
}

export function priceBandLabel(
  locale: Locale,
  amount: number,
  copy: Pick<ActiveFilterCopy, 'priceUpToLabel'>,
): string {
  return formatTemplate(copy.priceUpToLabel, { amount: formatMoney(locale, amount, 'hkd') });
}

/** The filters a search applies, in the order the search bar shows them. */
export function activeFilters(
  locale: Locale,
  filters: SearchFiltersState,
  copy: ActiveFilterCopy,
): readonly ActiveFilter[] {
  const chips: ActiveFilter[] = [];
  const place = placeLabelForFilters(filters, locale);
  if (place) {
    chips.push({
      id: 'place',
      label: place,
      without: filters.neighbourhoodId
        ? { ...filters, neighbourhoodId: null }
        : { ...filters, regionId: null, neighbourhoodId: null },
    });
  }
  const ageGroup = homeWizardChoices.ageGroups.find((group) => group.id === filters.ageGroupId);
  chips.push(
    ageGroup
      ? {
          id: 'age',
          label: labelForLocale(ageGroup.labels, locale),
          without: { ...filters, ageGroupId: null },
        }
      : { id: 'age', label: copy.allAgesLabel, without: null },
  );
  for (const typeId of filters.activityTypeIds) {
    const type = homeWizardChoices.activityTypes.find((entry) => entry.id === typeId);
    if (type) {
      chips.push({
        id: `type-${typeId}`,
        label: labelForLocale(type.labels, locale),
        without: {
          ...filters,
          activityTypeIds: filters.activityTypeIds.filter((id) => id !== typeId),
        },
      });
    }
  }
  const query = filters.textQuery.trim();
  if (query) {
    chips.push({ id: 'query', label: `“${query}”`, without: { ...filters, textQuery: '' } });
  }
  if (filters.free) {
    chips.push({ id: 'free', label: copy.freeFilterLabel, without: { ...filters, free: false } });
  }
  if (filters.freeTrial) {
    chips.push({
      id: 'trial',
      label: copy.freeTrialFilterLabel,
      without: { ...filters, freeTrial: false },
    });
  }
  if (filters.day) {
    chips.push({
      id: 'day',
      label: dayChoiceLabel(locale, filters.day, copy),
      without: { ...filters, day: null },
    });
  }
  if (filters.language) {
    chips.push({
      id: 'language',
      label: languageLabel(locale, filters.language),
      without: { ...filters, language: null },
    });
  }
  if (filters.classPriceMax !== null && filters.classPriceMax !== undefined) {
    chips.push({
      id: 'price',
      label: priceBandLabel(locale, filters.classPriceMax, copy),
      without: { ...filters, classPriceMax: null },
    });
  }
  return chips;
}

/** Keeps the place and drops every other filter. */
export function clearedFilters(filters: SearchFiltersState): SearchFiltersState {
  return {
    ageGroupId: null,
    regionId: filters.regionId,
    neighbourhoodId: filters.neighbourhoodId,
    activityTypeIds: [],
    textQuery: '',
    ...(filters.sort ? { sort: filters.sort } : {}),
  };
}
