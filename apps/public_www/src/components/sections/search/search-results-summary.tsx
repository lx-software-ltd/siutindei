'use client';

import type { ReactNode } from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { SearchSortSelect } from '@/components/sections/search/search-sort-select';
import { activeFilters, clearedFilters } from '@/lib/activities/active-filters';
import type { SearchFiltersState } from '@/lib/activities/search-params';
import { formatTemplate } from '@/lib/format-template';

interface SearchResultsSummaryProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
  readonly filters: SearchFiltersState;
  readonly total: number | null;
  readonly isLoading: boolean;
  readonly onApply: (next: SearchFiltersState) => void;
  readonly viewToggle?: ReactNode;
}

/** The one filter phones cannot see or change in the search bar or the filter row. */
const PHONE_CHIP_ID = 'query';

export function resultCountText(
  copy: Pick<SiteContent['searchPage'], 'resultCountLabel' | 'resultCountSingleLabel'>,
  total: number,
): string {
  return total === 1
    ? copy.resultCountSingleLabel
    : formatTemplate(copy.resultCountLabel, { count: total.toLocaleString('en-HK') });
}

/**
 * The count, the applied filters, sorting, and the view switch. Phones keep
 * the screen for results: the search bar already names the place, age, and
 * types, the filter row shows its own choices and carries sorting and the
 * view switch, and the count is read out but not shown.
 */
export function SearchResultsSummary({
  locale,
  copy,
  filters,
  total,
  isLoading,
  onApply,
  viewToggle,
}: SearchResultsSummaryProps) {
  const chips = activeFilters(locale, filters, copy);
  const removable = chips.filter((chip) => chip.without !== null);
  const showsOnPhones = chips.some((chip) => chip.id === PHONE_CHIP_ID);

  return (
    <div
      className={`search-results-summary mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 sm:px-6 md:pt-3 lg:px-8 ${
        showsOnPhones ? 'pt-2' : ''
      }`}
    >
      <p
        role="status"
        aria-live="polite"
        className="text-sm font-semibold text-ink-900 max-md:sr-only"
      >
        {isLoading || total === null ? '\u00a0' : resultCountText(copy, total)}
      </p>
      <ul aria-label={copy.activeFiltersLabel} className="flex min-w-0 flex-wrap items-center gap-2">
        {chips.map((chip) => (
          <li key={chip.id} className={chip.id === PHONE_CHIP_ID ? '' : 'max-md:hidden'}>
            {chip.without ? (
              <button
                type="button"
                onClick={() => chip.without && onApply(chip.without)}
                aria-label={formatTemplate(copy.removeFilterLabel, { label: chip.label })}
                className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-brand-50 py-1 pl-3 pr-2 text-sm text-ink-900 hover:bg-brand-100"
              >
                {chip.label}
                <img
                  src="/images/icons/close.svg"
                  alt=""
                  width={14}
                  height={14}
                  aria-hidden="true"
                  className="h-3.5 w-3.5"
                />
              </button>
            ) : (
              <span className="inline-flex min-h-9 items-center rounded-full border border-brand-100 px-3 py-1 text-sm text-ink-700">
                {chip.label}
              </span>
            )}
          </li>
        ))}
        {removable.length > 1 ? (
          <li className="max-md:hidden">
            <button
              type="button"
              onClick={() => onApply(clearedFilters(filters))}
              className="min-h-9 px-2 text-sm font-semibold text-ink-900 underline underline-offset-2"
            >
              {copy.clearFiltersLabel}
            </button>
          </li>
        ) : null}
      </ul>
      <div className="ml-auto flex items-center gap-2 max-md:hidden">
        <SearchSortSelect copy={copy} filters={filters} onApply={onApply} />
        {viewToggle}
      </div>
    </div>
  );
}
