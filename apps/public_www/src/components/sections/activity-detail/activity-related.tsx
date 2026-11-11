'use client';

import { useEffect, useState } from 'react';

import type { Locale } from '@/content/locales';
import { ListingCard, type ListingCardLabels } from '@/components/sections/listings/listing-card';
import { Carousel } from '@/components/shared/ui/carousel';
import { groupListings } from '@/lib/activities/group-listings';
import { logActivityLoadError } from '@/lib/activities/load-error';
import { fetchActivitySearch } from '@/lib/activities/search-client';
import type { ActivityListing, ActivitySearchParams } from '@/lib/activities/types';

const RELATED_ROWS = 24;
const RELATED_SHOWN = 8;

interface ActivityRelatedProps {
  readonly locale: Locale;
  readonly id: string;
  readonly title: string;
  readonly params: ActivitySearchParams | null;
  readonly excludeIds: readonly string[];
  readonly labels: ListingCardLabels;
  readonly previousLabel: string;
  readonly nextLabel: string;
  readonly onLoaded?: (ids: readonly string[]) => void;
}

/** A carousel of other activities. Renders nothing until it has results. */
export function ActivityRelated({
  locale,
  id,
  title,
  params,
  excludeIds,
  labels,
  previousLabel,
  nextLabel,
  onLoaded,
}: ActivityRelatedProps) {
  const [listings, setListings] = useState<readonly ActivityListing[]>([]);
  const paramsKey = JSON.stringify(params);
  const excludeKey = excludeIds.join(',');

  useEffect(() => {
    if (!params) {
      setListings([]);
      return undefined;
    }
    const controller = new AbortController();
    const excluded = new Set(excludeKey.split(','));
    fetchActivitySearch(
      { ...params, limit: RELATED_ROWS, view: 'card' },
      { signal: controller.signal },
    )
      .then((response) => {
        const next = groupListings(response.items)
          .filter((listing) => !excluded.has(listing.activity.id))
          .slice(0, RELATED_SHOWN);
        setListings(next);
        onLoaded?.(next.map((listing) => listing.activity.id));
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          logActivityLoadError(`activity ${id}`, error);
          setListings([]);
        }
      });
    return () => controller.abort();
    // paramsKey and excludeKey are the stable identities of params and excludeIds.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, paramsKey, excludeKey]);

  if (listings.length === 0) {
    return null;
  }

  const headingId = `${id}-heading`;
  return (
    <section id={id} aria-labelledby={headingId} className="border-t border-brand-100 pt-6">
      <h2 id={headingId} className="text-xl font-semibold text-ink-900">
        {title}
      </h2>
      <div className="mt-4">
        <Carousel ariaLabel={title} previousLabel={previousLabel} nextLabel={nextLabel}>
          {listings.map((listing) => (
            <ListingCard
              key={listing.activity.id}
              locale={locale}
              listing={listing}
              labels={labels}
            />
          ))}
        </Carousel>
      </div>
    </section>
  );
}
