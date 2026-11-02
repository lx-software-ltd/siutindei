'use client';

import Link from 'next/link';

import type { Locale } from '@/content/locales';
import {
  buildMapSearchHref,
  buildMapSearchHrefForRegion,
} from '@/lib/activities/map-search-url';
import type { SearchFiltersState } from '@/lib/activities/search-params';

interface RegionMapLinkProps {
  readonly locale: Locale;
  readonly label: string;
  readonly filters: SearchFiltersState;
  readonly regionId?: string | null;
  readonly className?: string;
}

export function RegionMapLink({
  locale,
  label,
  filters,
  regionId,
  className = '',
}: RegionMapLinkProps) {
  const href =
    regionId != null && regionId !== ''
      ? buildMapSearchHrefForRegion(locale, filters, regionId)
      : buildMapSearchHref(locale, filters);

  return (
    <Link
      href={href}
      className={`font-medium text-brand-600 underline-offset-2 hover:underline ${className}`.trim()}
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      {label}
    </Link>
  );
}
