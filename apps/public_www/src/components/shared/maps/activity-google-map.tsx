'use client';

import { useEffect, useId, useRef } from 'react';

import type { Locale } from '@/content/locales';
import {
  centerForCoordinates,
  HONG_KONG_CENTER,
  listingCoordinate,
  listingsWithCoordinates,
} from '@/lib/google-maps/coordinates';
import { loadGoogleMapsScript } from '@/lib/google-maps/load-script';
import { getGoogleMapsConfig } from '@/lib/google-maps/config';
import { listingTitle } from '@/lib/activities/listing-utils';
import { iconSrcForActivityCategory } from '@/lib/home-wizard/choice-icons';
import type { ActivityListing } from '@/lib/activities/types';

interface ActivityGoogleMapProps {
  readonly locale: Locale;
  readonly listings: readonly ActivityListing[];
  readonly selectedId: string | null;
  readonly onSelect: (activityId: string) => void;
  readonly className?: string;
  readonly ariaLabel: string;
}

const MARKER_SIZE = 36;
const SELECTED_MARKER_SIZE = 48;

function hasSize(element: HTMLElement): boolean {
  return element.clientWidth > 0 && element.clientHeight > 0;
}

async function whenContainerHasSize(element: HTMLElement): Promise<void> {
  if (hasSize(element)) {
    return;
  }

  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });

  if (hasSize(element) || typeof ResizeObserver !== 'function') {
    return;
  }

  await new Promise<void>((resolve) => {
    const observer = new ResizeObserver(() => {
      if (hasSize(element)) {
        observer.disconnect();
        window.clearTimeout(timeoutId);
        resolve();
      }
    });
    observer.observe(element);
    const timeoutId = window.setTimeout(() => {
      observer.disconnect();
      resolve();
    }, 400);
  });
}

function markerIconUrl(categoryId: string | null): string {
  const src = iconSrcForActivityCategory(categoryId);
  if (typeof window === 'undefined') {
    return src;
  }
  return new URL(src, window.location.origin).href;
}

function markerIcon(
  categoryId: string | null,
  isSelected: boolean,
): google.maps.Icon {
  const size = isSelected ? SELECTED_MARKER_SIZE : MARKER_SIZE;
  return {
    url: markerIconUrl(categoryId),
    scaledSize: new google.maps.Size(size, size),
    anchor: new google.maps.Point(size / 2, size),
  };
}

function coordinatesFor(
  listings: readonly ActivityListing[],
): readonly NonNullable<ReturnType<typeof listingCoordinate>>[] {
  return listingsWithCoordinates(listings)
    .map((listing) => listingCoordinate(listing))
    .filter((value): value is NonNullable<typeof value> => value !== null);
}

function syncMarkers(options: {
  readonly map: google.maps.Map;
  readonly listings: readonly ActivityListing[];
  readonly locale: Locale;
  readonly selectedId: string | null;
  readonly onSelect: (activityId: string) => void;
  readonly markers: Map<string, google.maps.Marker>;
}): void {
  const { map, listings, locale, selectedId, onSelect, markers } = options;
  const mappableListings = listingsWithCoordinates(listings);
  const coordinates = coordinatesFor(listings);
  const bounds = new google.maps.LatLngBounds();
  const seen = new Set<string>();

  for (const listing of mappableListings) {
    const coordinate = listingCoordinate(listing);
    if (!coordinate) {
      continue;
    }
    const position = new google.maps.LatLng(coordinate.lat, coordinate.lng);
    bounds.extend(position);
    seen.add(listing.activity.id);
    const icon = markerIcon(
      listing.activity.categoryId,
      listing.activity.id === selectedId,
    );
    const title = listingTitle(locale, listing);
    const existing = markers.get(listing.activity.id);
    if (existing) {
      existing.setPosition(position);
      existing.setIcon(icon);
      existing.setTitle(title);
      continue;
    }
    const marker = new google.maps.Marker({
      map,
      position,
      title,
      icon,
    });
    marker.addListener('click', () => {
      onSelect(listing.activity.id);
    });
    markers.set(listing.activity.id, marker);
  }

  for (const [activityId, marker] of markers) {
    if (!seen.has(activityId)) {
      marker.setMap(null);
      markers.delete(activityId);
    }
  }

  if (coordinates.length > 1) {
    map.fitBounds(bounds, 48);
  } else if (coordinates.length === 1) {
    map.setCenter(
      new google.maps.LatLng(coordinates[0].lat, coordinates[0].lng),
    );
    map.setZoom(14);
  }
}

export function ActivityGoogleMap({
  locale,
  listings,
  selectedId,
  onSelect,
  className = '',
  ariaLabel,
}: ActivityGoogleMapProps) {
  const containerId = useId().replace(/:/g, '');
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<Map<string, google.maps.Marker>>(new Map());
  const listingsRef = useRef(listings);
  const localeRef = useRef(locale);
  const selectedIdRef = useRef(selectedId);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    listingsRef.current = listings;
  }, [listings]);
  useEffect(() => {
    localeRef.current = locale;
  }, [locale]);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  const listingIds = listings.map((listing) => listing.activity.id).join(',');

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const apiKey = getGoogleMapsConfig().apiKey;
    if (!apiKey) {
      return;
    }

    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;

    loadGoogleMapsScript(apiKey)
      .then(async () => {
        if (cancelled || !containerRef.current) {
          return;
        }

        await whenContainerHasSize(containerRef.current);
        if (cancelled || !containerRef.current) {
          return;
        }

        const coordinates = coordinatesFor(listingsRef.current);
        const center = centerForCoordinates(
          coordinates.length > 0 ? coordinates : [HONG_KONG_CENTER],
        );
        const centerLatLng = new google.maps.LatLng(center.lat, center.lng);

        const map =
          mapRef.current ??
          new google.maps.Map(containerRef.current, {
            center: centerLatLng,
            zoom: coordinates.length === 1 ? 14 : 11,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
          });
        mapRef.current = map;
        google.maps.event.trigger(map, 'resize');
        map.setCenter(centerLatLng);
        syncMarkers({
          map,
          listings: listingsRef.current,
          locale: localeRef.current,
          selectedId: selectedIdRef.current,
          onSelect: (activityId) => onSelectRef.current(activityId),
          markers: markersRef.current,
        });

        if (typeof ResizeObserver === 'function') {
          resizeObserver = new ResizeObserver(() => {
            const sizedContainer = containerRef.current;
            if (!sizedContainer || !hasSize(sizedContainer)) {
              return;
            }
            google.maps.event.trigger(map, 'resize');
          });
          resizeObserver.observe(containerRef.current);
        }
      })
      .catch(() => {
        // Map load errors are surfaced by the parent empty state.
      });

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    syncMarkers({
      map,
      listings,
      locale,
      selectedId: selectedIdRef.current,
      onSelect,
      markers: markersRef.current,
    });
  }, [listingIds, listings, locale, onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedId) {
      return;
    }

    const listing = listings.find((entry) => entry.activity.id === selectedId);
    const coordinate = listing ? listingCoordinate(listing) : null;
    if (!coordinate) {
      return;
    }

    for (const [activityId, marker] of markersRef.current) {
      const entry = listings.find((item) => item.activity.id === activityId);
      marker.setIcon(
        markerIcon(
          entry?.activity.categoryId ?? null,
          activityId === selectedId,
        ),
      );
    }

    map.panTo(new google.maps.LatLng(coordinate.lat, coordinate.lng));
    if (listingsWithCoordinates(listings).length === 1) {
      map.setZoom(14);
    }
  }, [listings, selectedId]);

  return (
    <div
      id={containerId}
      ref={containerRef}
      className={`activity-google-map ${className}`.trim()}
      role="application"
      aria-label={ariaLabel}
    />
  );
}
