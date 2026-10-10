'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import type { Locale } from '@/content';
import { useSearchContext } from '@/components/shared/search/search-context';
import { buildMapSearchHref } from '@/lib/activities/map-search-url';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';
import {
  areaIdForFilters,
  buildSearchQueryString,
  searchAgeForGroup,
} from '@/lib/activities/search-params';
import { localizePath } from '@/lib/locale-routing';

interface SearchBarCompactProps {
  readonly locale: Locale;
  readonly labels: {
    readonly where: string;
    readonly childAge: string;
    readonly activityTypes: string;
    readonly search: string;
    readonly anywhere: string;
    readonly anyAge: string;
    readonly anyType: string;
    readonly openMapForAreaLabel: string;
  };
}

function summarizeTypes(
  locale: Locale,
  typeIds: readonly string[],
): string {
  if (typeIds.length === 0) {
    return '';
  }
  const labels = typeIds
    .map((id) => {
      const match = homeWizardChoices.activityTypes.find(
        (entry) => entry.id === id,
      );
      return match ? labelForLocale(match.labels, locale) : null;
    })
    .filter((value): value is string => Boolean(value));
  if (labels.length === 0) {
    return '';
  }
  if (labels.length === 1) {
    return labels[0];
  }
  return `${labels[0]} +${labels.length - 1}`;
}

export function SearchBarCompact({ locale, labels }: SearchBarCompactProps) {
  const router = useRouter();
  const { filters, openSearch } = useSearchContext();

  const region = homeWizardChoices.regions.find(
    (entry) => entry.id === filters.regionId,
  );
  const neighbourhood = homeWizardChoices.neighbourhoods.find(
    (entry) => entry.id === filters.neighbourhoodId,
  );
  const ageGroup = homeWizardChoices.ageGroups.find(
    (entry) => entry.id === filters.ageGroupId,
  );

  const whereLabel = neighbourhood
    ? labelForLocale(neighbourhood.labels, locale)
    : region
      ? labelForLocale(region.labels, locale)
      : labels.anywhere;
  const ageLabel = ageGroup
    ? labelForLocale(ageGroup.labels, locale)
    : labels.anyAge;
  const typesLabel =
    summarizeTypes(locale, filters.activityTypeIds) || labels.anyType;

  const hasArea = Boolean(areaIdForFilters(filters));
  const hasAge = Boolean(searchAgeForGroup(filters.ageGroupId));
  const mapHref = buildMapSearchHref(locale, filters);
  const searchHref = (() => {
    const query = buildSearchQueryString(filters);
    const path = localizePath('/search', locale);
    return query ? `${path}?${query}` : path;
  })();

  function handleSearchNavigate() {
    router.push(searchHref);
  }

  return (
    <div
      className="search-bar-compact flex w-full max-w-3xl items-center rounded-full border border-ink-900/15 bg-white py-1 pl-4 pr-1 shadow-sm"
      role="search"
    >
      <span className="hidden min-w-0 flex-1 grid-cols-3 divide-x divide-ink-900/10 md:grid">
        <Link
          href={mapHref}
          className="link-unadorned truncate px-3 py-2 text-left transition hover:bg-brand-50"
          aria-label={`${labels.openMapForAreaLabel}: ${whereLabel}`}
          onClick={(event) => event.stopPropagation()}
        >
          <span className="block text-xs font-semibold text-ink-900">
            {labels.where}
          </span>
          <span className="block truncate text-sm text-brand-600">
            {whereLabel}
          </span>
        </Link>
        <button
          type="button"
          className="truncate px-3 py-2 text-left transition hover:bg-brand-50"
          onClick={openSearch}
        >
          <span className="block text-xs font-semibold text-ink-900">
            {labels.childAge}
          </span>
          <span className="block truncate text-sm text-ink-500">{ageLabel}</span>
        </button>
        <button
          type="button"
          className="truncate px-3 py-2 text-left transition hover:bg-brand-50"
          onClick={openSearch}
        >
          <span className="block text-xs font-semibold text-ink-900">
            {labels.activityTypes}
          </span>
          <span className="block truncate text-sm text-ink-500">
            {typesLabel}
          </span>
        </button>
      </span>
      <button
        type="button"
        className="min-w-0 flex-1 truncate px-2 py-2 text-left text-sm text-ink-700 md:hidden"
        onClick={openSearch}
        aria-label={labels.search}
      >
        {[whereLabel, ageLabel, typesLabel]
          .filter((value, index) => {
            if (index === 0) {
              return hasArea || !hasAge;
            }
            return true;
          })
          .join(' · ')}
      </button>
      <button
        type="button"
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-500 text-lg text-ink-900 ring-2 ring-inset ring-ink-900/20 transition hover:bg-accent-600"
        aria-label={labels.search}
        onClick={handleSearchNavigate}
      >
        ⌕
      </button>
    </div>
  );
}
