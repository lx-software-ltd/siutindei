'use client';

import { useEffect, useRef, useState } from 'react';

import type { ActivityListing } from '@/lib/activities/types';
import { listingCoordinate } from '@/lib/google-maps/coordinates';
import {
  getGoogleMapsConfig,
  isGoogleMapsEnabled,
} from '@/lib/google-maps/config';
import { buildStaticMapUrl } from '@/lib/google-maps/static-map-url';
import { listingTitle } from '@/lib/activities/listing-utils';
import type { Locale } from '@/content/locales';
interface ListingCardMiniMapProps {
  readonly locale: Locale;
  readonly listing: ActivityListing;
  readonly mapAltLabel: string;
}

export function ListingCardMiniMap({
  locale,
  listing,
  mapAltLabel,
}: ListingCardMiniMapProps) {
  const mapsEnabled = isGoogleMapsEnabled();
  const coordinate = listingCoordinate(listing);
  const latitude = coordinate?.lat;
  const longitude = coordinate?.lng;
  const containerRef = useRef<HTMLDivElement>(null);
  const [isNear, setIsNear] = useState(false);

  useEffect(() => {
    if (!mapsEnabled || latitude === undefined || longitude === undefined) {
      return;
    }
    const node = containerRef.current;
    if (!node || typeof IntersectionObserver === 'undefined') {
      setIsNear(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setIsNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
    };
  }, [latitude, longitude, mapsEnabled]);

  if (!mapsEnabled || !coordinate) {
    return null;
  }

  const { apiKey } = getGoogleMapsConfig();
  const title = listingTitle(locale, listing);
  const mapUrl = isNear
    ? buildStaticMapUrl({
        apiKey,
        coordinate,
        variant: 'card',
        zoom: 15,
        scale: 1,
      })
    : null;
  const mapUrl2x = isNear
    ? buildStaticMapUrl({
        apiKey,
        coordinate,
        variant: 'card',
        zoom: 15,
        scale: 2,
      })
    : null;

  return (
    <div
      ref={containerRef}
      className="listing-card-mini-map pointer-events-none absolute inset-x-0 bottom-0 h-[38%] overflow-hidden rounded-b-xl border-t border-white/80"
    >
      {mapUrl ? (
        <img
          src={mapUrl}
          alt={`${mapAltLabel}: ${title}`}
          width={600}
          height={200}
          srcSet={`${mapUrl} 1x, ${mapUrl2x} 2x`}
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover"
        />
      ) : null}
    </div>
  );
}
