'use client';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { Chip } from '@/components/shared/ui/chip';
import { ChipSelect } from '@/components/shared/ui/chip-select';
import { useSearchContext } from '@/components/shared/search/search-context';
import { useApplySearchFilters } from '@/components/sections/search/use-apply-search-filters';
import { dayChoiceLabel, priceBandLabel } from '@/lib/activities/active-filters';
import { languageLabel } from '@/lib/activities/listing-facts';
import {
  SEARCH_LANGUAGE_CODES,
  SEARCH_PRICE_BANDS,
  type SearchDayChoice,
} from '@/lib/activities/search-params';

interface FilterChipRowProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
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

export function FilterChipRow({ locale, copy }: FilterChipRowProps) {
  const { filters } = useSearchContext();
  const applyFilters = useApplySearchFilters(locale);

  return (
    <div className="border-b border-brand-100 bg-white">
      <div
        role="group"
        aria-label={copy.filtersLabel}
        className="mx-auto flex max-w-7xl items-center gap-2 overflow-x-auto px-4 py-3 [justify-content:safe_center] sm:px-6 lg:px-8"
      >
        <Chip
          isSelected={filters.free === true}
          aria-pressed={filters.free === true}
          onClick={() => applyFilters({ ...filters, free: !filters.free })}
        >
          {copy.freeFilterLabel}
        </Chip>
        <Chip
          isSelected={filters.freeTrial === true}
          aria-pressed={filters.freeTrial === true}
          onClick={() => applyFilters({ ...filters, freeTrial: !filters.freeTrial })}
        >
          {copy.freeTrialFilterLabel}
        </Chip>
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
      </div>
    </div>
  );
}
