'use client';

import type { ReactNode } from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { Chip } from '@/components/shared/ui/chip';
import { ChipSelect } from '@/components/shared/ui/chip-select';
import { useSearchContext } from '@/components/shared/search/search-context';
import { SearchSortSelect } from '@/components/sections/search/search-sort-select';
import { useApplySearchFilters } from '@/components/sections/search/use-apply-search-filters';
import { dayChoiceLabel, priceBandLabel } from '@/lib/activities/active-filters';
import { languageLabel } from '@/lib/activities/listing-facts';
import {
  kindHasClassFilters,
  SEARCH_LANGUAGE_CODES,
  SEARCH_PRICE_BANDS,
  withKind,
  type SearchDayChoice,
} from '@/lib/activities/search-params';
import { useOfferedKinds } from '@/components/shared/offered-kinds';
import { labelForLocale } from '@/lib/home-wizard/choices';

interface FilterChipRowProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
  /** The list and map switch. Phones pin it to the end of this row. */
  readonly viewToggle?: ReactNode;
  /** Phones sort from this row. The map view has nothing to sort on screen. */
  readonly isMapView?: boolean;
}

const DAY_CHOICES: readonly SearchDayChoice[] = [
  'weekend',
  'weekdays',
  '1',
  '2',
  '3',
  '4',
  '5',
  '6',
  '0',
];

export function FilterChipRow({
  locale,
  copy,
  viewToggle,
  isMapView = false,
}: FilterChipRowProps) {
  const { filters } = useSearchContext();
  const applyFilters = useApplySearchFilters(locale);
  const offeredKinds = useOfferedKinds();
  const classFilters = kindHasClassFilters(filters.kind);

  return (
    <div className="search-toolbar flex shrink-0 items-center border-b border-brand-100 bg-white">
      <div
        role="group"
        aria-label={copy.filtersLabel}
        className="mx-auto flex min-w-0 max-w-7xl flex-1 items-center gap-2 overflow-x-auto px-4 py-1.5 [justify-content:safe_center] max-md:[scrollbar-width:none] sm:px-6 md:py-3 lg:px-8"
      >
        <ChipSelect
          label={copy.kindFilterLabel}
          value={filters.kind ?? ''}
          options={[
            { value: '', label: copy.anyKindLabel },
            ...offeredKinds.map((kind) => ({
              value: kind.id,
              label: labelForLocale(kind.labels, locale),
            })),
          ]}
          onValueChange={(value) => applyFilters(withKind(filters, value || null))}
        />
        <Chip
          isSelected={filters.free === true}
          aria-pressed={filters.free === true}
          onClick={() => applyFilters({ ...filters, free: !filters.free })}
        >
          {copy.freeFilterLabel}
        </Chip>
        {classFilters ? (
          <Chip
            isSelected={filters.freeTrial === true}
            aria-pressed={filters.freeTrial === true}
            onClick={() => applyFilters({ ...filters, freeTrial: !filters.freeTrial })}
          >
            {copy.freeTrialFilterLabel}
          </Chip>
        ) : null}
        <ChipSelect
          label={copy.dayFilterLabel}
          value={filters.day ?? ''}
          options={[
            { value: '', label: copy.anyDayLabel },
            ...DAY_CHOICES.map((day) => ({ value: day, label: dayChoiceLabel(locale, day, copy) })),
          ]}
          onValueChange={(value) =>
            applyFilters({ ...filters, day: value ? (value as SearchDayChoice) : null })
          }
        />
        <ChipSelect
          label={copy.languageFilterLabel}
          value={filters.language ?? ''}
          options={[
            { value: '', label: copy.anyLanguageLabel },
            ...SEARCH_LANGUAGE_CODES.map((code) => ({
              value: code,
              label: languageLabel(locale, code),
            })),
          ]}
          onValueChange={(value) => applyFilters({ ...filters, language: value || null })}
        />
        {classFilters ? (
          <ChipSelect
            label={copy.priceFilterLabel}
            value={
              filters.classPriceMax === null || filters.classPriceMax === undefined
                ? ''
                : String(filters.classPriceMax)
            }
            options={[
              { value: '', label: copy.anyPriceLabel },
              ...SEARCH_PRICE_BANDS.map((amount) => ({
                value: String(amount),
                label: priceBandLabel(locale, amount, copy),
              })),
            ]}
            onValueChange={(value) =>
              applyFilters({ ...filters, classPriceMax: value ? Number(value) : null })
            }
          />
        ) : null}
        {isMapView ? null : (
          <SearchSortSelect
            copy={copy}
            filters={filters}
            onApply={applyFilters}
            namesItself
            className="md:hidden"
          />
        )}
      </div>
      {viewToggle ? (
        <div className="shrink-0 border-l border-brand-100 py-1.5 pl-2 pr-4 sm:pr-6 md:hidden">
          {viewToggle}
        </div>
      ) : null}
    </div>
  );
}
