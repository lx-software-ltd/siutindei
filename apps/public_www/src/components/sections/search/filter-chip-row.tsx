'use client';

import { useRouter, useSearchParams } from 'next/navigation';

import type { Locale } from '@/content/locales';
import { Chip } from '@/components/shared/ui/chip';
import { useSearchContext } from '@/components/shared/search/search-context';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';
import { iconSrcForActivity } from '@/lib/home-wizard/choice-icons';
import {
  parseSearchViewMode,
  toggleActivityTypeId,
} from '@/lib/activities/search-params';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';

interface FilterChipRowProps {
  readonly locale: Locale;
}

export function FilterChipRow({ locale }: FilterChipRowProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { filters, setFilters } = useSearchContext();

  function toggleType(typeId: string) {
    const nextFilters = toggleActivityTypeId(filters, typeId);
    setFilters(nextFilters);
    const viewMode = parseSearchViewMode(searchParams);
    router.replace(buildSearchPageHref(locale, nextFilters, { view: viewMode }));
  }

  return (
    <div className="border-b border-brand-100 bg-white">
      <div className="mx-auto flex max-w-7xl gap-2 overflow-x-auto px-4 py-3 sm:px-6 lg:px-8">
        {homeWizardChoices.activityTypes.map((type) => (
          <Chip
            key={type.id}
            isSelected={filters.activityTypeIds.includes(type.id)}
            onClick={() => toggleType(type.id)}
          >
            <img
              src={iconSrcForActivity(type.id)}
              alt=""
              width={20}
              height={20}
              decoding="async"
              aria-hidden="true"
              className="h-5 w-5 object-contain"
            />
            {labelForLocale(type.labels, locale)}
          </Chip>
        ))}
      </div>
    </div>
  );
}
