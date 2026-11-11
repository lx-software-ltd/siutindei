'use client';

import { useState } from 'react';

import type { Locale } from '@/content/locales';
import { directionsUrl, placeLabelForLocation } from '@/lib/activities/listing-facts';
import type { SearchLocation } from '@/lib/activities/types';
import { getGoogleMapsConfig, isGoogleMapsEnabled } from '@/lib/google-maps/config';
import { buildStaticMapUrl } from '@/lib/google-maps/static-map-url';

import { DetailIcon } from './detail-icon';
import { DetailSection } from './detail-section';
import type { ActivityDetailCopy } from './types';

interface ActivityLocationProps {
  readonly locale: Locale;
  readonly venues: readonly SearchLocation[];
  readonly selectedId: string;
  readonly onSelect: (locationId: string) => void;
  readonly placeId: string | null;
  readonly copy: ActivityDetailCopy;
}

function StaticMap({
  location,
  alt,
}: {
  readonly location: SearchLocation;
  readonly alt: string;
}) {
  const [failedKey, setFailedKey] = useState<string | null>(null);
  if (!isGoogleMapsEnabled() || location.lat === null || location.lng === null) {
    return null;
  }
  const key = `${location.lat},${location.lng}`;
  if (failedKey === key) {
    return null;
  }
  const coordinate = { lat: location.lat, lng: location.lng };
  const { apiKey } = getGoogleMapsConfig();
  return (
    <img
      src={buildStaticMapUrl({ apiKey, coordinate, variant: 'detail', zoom: 15, scale: 1 })}
      srcSet={`${buildStaticMapUrl({ apiKey, coordinate, variant: 'detail', zoom: 15, scale: 2 })} 2x`}
      alt={alt}
      width={800}
      height={400}
      loading="lazy"
      decoding="async"
      onError={() => setFailedKey(key)}
      className="mt-4 aspect-[2/1] w-full rounded-xl border border-brand-100 object-cover"
    />
  );
}

function VenueText({
  locale,
  location,
}: {
  readonly locale: Locale;
  readonly location: SearchLocation;
}) {
  const place = placeLabelForLocation(locale, location);
  return (
    <span className="min-w-0">
      {location.name ? (
        <span className="block font-semibold text-ink-900">{location.name}</span>
      ) : null}
      {place ? (
        <span className={location.name ? 'block text-sm text-ink-700' : 'block font-semibold text-ink-900'}>
          {place}
        </span>
      ) : null}
      {location.address ? (
        <span className="block text-sm text-ink-500">{location.address}</span>
      ) : null}
    </span>
  );
}

export function ActivityLocation({
  locale,
  venues,
  selectedId,
  onSelect,
  placeId,
  copy,
}: ActivityLocationProps) {
  const selected = venues.find((venue) => venue.id === selectedId) ?? venues[0];
  if (!selected) {
    return null;
  }
  const directions = directionsUrl(selected, venues.length === 1 ? placeId : null);
  return (
    <DetailSection id="location" title={copy.locationHeading}>
      {venues.length > 1 ? (
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink-700">{copy.chooseVenueLabel}</legend>
          <ul className="space-y-2">
            {venues.map((venue) => {
              const isSelected = venue.id === selected.id;
              return (
                <li key={venue.id}>
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => onSelect(venue.id)}
                    className={`flex min-h-11 w-full items-start gap-3 rounded-xl border p-3 text-left transition ${
                      isSelected
                        ? 'border-ink-900 bg-brand-50'
                        : 'border-brand-100 bg-white hover:border-brand-200'
                    }`}
                  >
                    <DetailIcon name={isSelected ? 'check' : 'pin'} className="mt-0.5 h-5 w-5" />
                    <VenueText locale={locale} location={venue} />
                  </button>
                </li>
              );
            })}
          </ul>
        </fieldset>
      ) : (
        <p className="flex gap-3">
          <DetailIcon name="pin" className="mt-0.5 h-5 w-5" />
          <VenueText locale={locale} location={selected} />
        </p>
      )}
      <StaticMap location={selected} alt={copy.mapAltLabel} />
      {directions ? (
        <a
          href={directions}
          target="_blank"
          rel="noreferrer noopener"
          className="link-unadorned mt-4 inline-flex min-h-11 items-center gap-2 rounded-lg border border-ink-900/15 bg-white px-4 text-sm font-semibold text-ink-900 hover:bg-brand-50"
        >
          <DetailIcon name="directions" className="h-[18px] w-[18px]" />
          {copy.directionsLabel}
        </a>
      ) : null}
    </DetailSection>
  );
}
