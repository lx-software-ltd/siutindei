'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import type { Locale } from '@/content/locales';
import { useSearchContext } from '@/components/shared/search/search-context';
import { buildMapSearchHref } from '@/lib/activities/map-search-url';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import { summarizeTypes } from '@/lib/activities/search/summarize-types';
import {
  searchPlaceLabel,
  withDefaultOpenLocation,
} from '@/lib/home-wizard/area-scope';

interface SearchBarCompactProps {
  readonly locale: Locale;
  readonly labels: {
    readonly where: string;
    readonly childAge: string;
    readonly activityTypes: string;
    readonly search: string;
    readonly anywhere: string;
    readonly allAreas: string;
    readonly noAreas: string;
    readonly anyAge: string;
    readonly anyType: string;
    readonly openMapForAreaLabel: string;
  };
}

export function SearchBarCompact({ locale, labels }: SearchBarCompactProps) {
  const router = useRouter();
  const { filters, openSearch } = useSearchContext();

  const ageGroup = homeWizardChoices.ageGroups.find(
    (entry) => entry.id === filters.ageGroupId,
  );

  const whereLabel = searchPlaceLabel(filters, locale, {
    anywhere: labels.anywhere,
    allAreas: labels.allAreas,
    noAreas: labels.noAreas,
  });
  const ageLabel = ageGroup
    ? labelForLocale(ageGroup.labels, locale)
    : labels.anyAge;
  const typesLabel =
    summarizeTypes(locale, filters.activityTypeIds) || labels.anyType;

  const located = withDefaultOpenLocation(filters);
  const mapHref = buildMapSearchHref(locale, located);
  const searchHref = buildSearchPageHref(locale, filters);

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
      {/* Phones: the place leads and the age and types sit under it, so the bar fits beside the logo. */}
      <button
        type="button"
        className="min-w-0 flex-1 py-0.5 pr-2 text-left md:hidden"
        onClick={openSearch}
        aria-label={labels.search}
      >
        <span className="block truncate text-sm font-semibold leading-5 text-ink-900">
          {whereLabel}
        </span>
        <span className="block truncate text-xs leading-4 text-ink-700">
          {`${ageLabel} · ${typesLabel}`}
        </span>
      </button>
      <button
        type="button"
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-500 text-[2.25rem] leading-none text-ink-900 ring-2 ring-inset ring-ink-900/20 transition hover:bg-accent-600"
        aria-label={labels.search}
        onClick={handleSearchNavigate}
      >
        ⌕
      </button>
    </div>
  );
}
