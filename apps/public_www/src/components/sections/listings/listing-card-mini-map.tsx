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

const VISIBLE_CLASS_NAME =
  'listing-card-mini-map pointer-events-none absolute inset-x-0 bottom-0 h-[38%] overflow-hidden rounded-b-xl border-t border-white/80';
const PENDING_CLASS_NAME =
  'pointer-events-none absolute inset-0 overflow-hidden opacity-0';

export function ListingCardMiniMap({
  locale,
  listing,
  mapAltLabel,
}: ListingCardMiniMapProps) {
  const mapsEnabled = isGoogleMapsEnabled();
  const coordinate = listingCoordinate(listing);
  const latitude = coordinate?.lat;
  const longitude = coordinate?.lng;
  const coordinateKey =
    latitude === undefined || longitude === undefined
      ? ''
      : `${latitude},${longitude}`;
  const containerRef = useRef<HTMLDivElement>(null);
  const [isNear, setIsNear] = useState(false);
  const [shownKey, setShownKey] = useState<string | null>(null);
  const [failedKey, setFailedKey] = useState<string | null>(null);

  useEffect(() => {
    if (!mapsEnabled || latitude === undefined || longitude === undefined) {
      return;
    }
    const node = containerRef.current;
    if (!node || typeof IntersectionObserver === 'undefined') {
      setIsNear(true);
      return;
    }
    setIsNear(false);
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

  if (!mapsEnabled || !coordinate || failedKey === coordinateKey) {
    return null;
  }

  const shown = shownKey === coordinateKey;
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
      className={shown ? VISIBLE_CLASS_NAME : PENDING_CLASS_NAME}
      aria-hidden={shown ? undefined : true}
    >
      {mapUrl ? (
        <img
          src={mapUrl}
          alt={shown ? `${mapAltLabel}: ${title}` : ''}
          width={600}
          height={200}
          srcSet={`${mapUrl} 1x, ${mapUrl2x} 2x`}
          loading="lazy"
          decoding="async"
          onLoad={() => setShownKey(coordinateKey)}
          onError={() => setFailedKey(coordinateKey)}
          className="h-full w-full object-cover"
        />
      ) : null}
    </div>
  );
}
