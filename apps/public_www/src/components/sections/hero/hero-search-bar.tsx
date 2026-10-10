'use client';

import { useRouter } from 'next/navigation';

import type { Locale, NavbarContent } from '@/content';
import { useSearchContext } from '@/components/shared/search/search-context';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';
import {
  buildSearchQueryString,
  placeLabelForFilters,
} from '@/lib/activities/search-params';
import { HERO_SEARCH_SENTINEL_ATTR } from '@/lib/home-header-reveal';
import { localizePath } from '@/lib/locale-routing';

type SearchBarLabels = NavbarContent['searchBar'];

interface HeroSearchBarProps {
  readonly locale: Locale;
  readonly labels: SearchBarLabels;
}

function summarizeTypes(
  locale: Locale,
  typeIds: readonly string[],
): string {
  const typeLabels = typeIds
    .map((id) => {
      const match = homeWizardChoices.activityTypes.find(
        (entry) => entry.id === id,
      );
      return match ? labelForLocale(match.labels, locale) : null;
    })
    .filter((value): value is string => Boolean(value));
  if (typeLabels.length === 0) {
    return '';
  }
  if (typeLabels.length === 1) {
    return typeLabels[0];
  }
  return `${typeLabels[0]} +${typeLabels.length - 1}`;
}

/**
 * The centralized "discovery" search bar for the Small World hero:
 * one clean pill focused on neighborhood, age group, and activity type.
 */
export function HeroSearchBar({ locale, labels }: HeroSearchBarProps) {
  const router = useRouter();
  const { filters, openSearch } = useSearchContext();

  const ageGroup = homeWizardChoices.ageGroups.find(
    (entry) => entry.id === filters.ageGroupId,
  );

  const whereLabel = placeLabelForFilters(filters, locale) ?? labels.anywhere;
  const ageLabel = ageGroup
    ? labelForLocale(ageGroup.labels, locale)
    : labels.anyAge;
  const typesLabel =
    summarizeTypes(locale, filters.activityTypeIds) || labels.anyType;

  function handleSearchNavigate() {
    const query = buildSearchQueryString(filters);
    const path = localizePath('/search', locale);
    router.push(query ? `${path}?${query}` : path);
  }

  const segments = [
    { key: 'where', label: labels.where, value: whereLabel },
    { key: 'age', label: labels.childAge, value: ageLabel },
    { key: 'types', label: labels.activityTypes, value: typesLabel },
  ];

  return (
    <div
      className="mx-auto flex w-full max-w-2xl items-center rounded-full border-2 border-ink-900/15 bg-white py-1.5 pl-2 pr-1.5 shadow-[0_18px_50px_rgba(46,29,18,0.28)]"
      {...{ [HERO_SEARCH_SENTINEL_ATTR]: '' }}
      role="search"
    >
      <span className="hidden min-w-0 flex-1 grid-cols-3 divide-x divide-ink-900/10 sm:grid">
        {segments.map((segment) => (
          <button
            key={segment.key}
            type="button"
            className="min-w-0 truncate rounded-full px-4 py-2.5 text-left transition hover:bg-brand-50"
            onClick={openSearch}
          >
            <span className="block text-xs font-semibold text-ink-900">
              {segment.label}
            </span>
            <span className="block truncate text-sm text-ink-500">
              {segment.value}
            </span>
          </button>
        ))}
      </span>
      <button
        type="button"
        className="min-w-0 flex-1 truncate px-3 py-2.5 text-left text-sm text-ink-700 sm:hidden"
        onClick={openSearch}
        aria-label={labels.search}
      >
        {[whereLabel, ageLabel, typesLabel].join(' · ')}
      </button>
      <button
        type="button"
        className="inline-flex h-12 shrink-0 items-center justify-center gap-2 rounded-full bg-accent-500 px-4 text-ink-900 ring-2 ring-inset ring-ink-900/20 transition hover:bg-accent-600 sm:px-5"
        aria-label={labels.search}
        onClick={handleSearchNavigate}
      >
        <span aria-hidden="true" className="text-xl">
          ⌕
        </span>
        <span className="hidden text-sm font-semibold md:inline">
          {labels.search}
        </span>
      </button>
    </div>
  );
}
