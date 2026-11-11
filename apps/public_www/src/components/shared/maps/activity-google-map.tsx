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
import {
  groupMarkers,
  markerIconSrc,
  nextIdInGroup,
  type MarkerGroup,
} from '@/lib/google-maps/marker-groups';
import { listingTitle } from '@/lib/activities/listing-utils';
import type { ActivityListing } from '@/lib/activities/types';
import { formatTemplate } from '@/lib/format-template';

interface ActivityGoogleMapProps {
  readonly locale: Locale;
  readonly listings: readonly ActivityListing[];
  readonly selectedId: string | null;
  readonly onSelect: (activityId: string) => void;
  readonly className?: string;
  readonly ariaLabel: string;
  /** Title of a pin shared by several activities, with `{count}`. */
  readonly groupLabel?: string;
}

const MARKER_WIDTH = 32;
const SELECTED_MARKER_WIDTH = 44;
const MARKER_ASPECT = 80 / 64;
const SELECTED_Z_INDEX = 1000;
const INK = '#2E1D12';

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

function absoluteUrl(src: string): string {
  if (typeof window === 'undefined') {
    return src;
  }
  return new URL(src, window.location.origin).href;
}

interface MarkerAppearance {
  readonly icon: google.maps.Icon;
  readonly label: google.maps.MarkerLabel | null;
  readonly zIndex: number;
}

function markerAppearance(group: MarkerGroup, selectedId: string | null): MarkerAppearance {
  const isSelected = selectedId !== null && group.ids.includes(selectedId);
  const width = isSelected ? SELECTED_MARKER_WIDTH : MARKER_WIDTH;
  const height = Math.round(width * MARKER_ASPECT);
  return {
    icon: {
      url: absoluteUrl(markerIconSrc(group, isSelected)),
      scaledSize: new google.maps.Size(width, height),
      anchor: new google.maps.Point(width / 2, height),
      labelOrigin: new google.maps.Point(width / 2, Math.round(height * 0.38)),
    },
    label:
      group.ids.length > 1
        ? {
            text: String(group.ids.length),
            color: INK,
            fontSize: isSelected ? '15px' : '13px',
            fontWeight: '700',
          }
        : null,
    zIndex: isSelected ? SELECTED_Z_INDEX : group.ids.length,
  };
}

function markerTitle(
  group: MarkerGroup,
  listings: readonly ActivityListing[],
  locale: Locale,
  groupLabel: string,
): string {
  if (group.ids.length > 1) {
    return formatTemplate(groupLabel, { count: group.ids.length });
  }
  const listing = listings.find((entry) => entry.activity.id === group.ids[0]);
  return listing ? listingTitle(locale, listing) : '';
}

function coordinatesFor(
  listings: readonly ActivityListing[],
): readonly NonNullable<ReturnType<typeof listingCoordinate>>[] {
  return listingsWithCoordinates(listings)
    .map((listing) => listingCoordinate(listing))
    .filter((value): value is NonNullable<typeof value> => value !== null);
}

interface PlacedMarker {
  readonly marker: google.maps.Marker;
  group: MarkerGroup;
}

function applyAppearance(placed: PlacedMarker, selectedId: string | null): void {
  const appearance = markerAppearance(placed.group, selectedId);
  placed.marker.setIcon(appearance.icon);
  placed.marker.setLabel(appearance.label);
  placed.marker.setZIndex(appearance.zIndex);
}

function syncMarkers(options: {
  readonly map: google.maps.Map;
  readonly listings: readonly ActivityListing[];
  readonly locale: Locale;
  readonly groupLabel: string;
  readonly selectedId: () => string | null;
  readonly onSelect: (activityId: string) => void;
  readonly markers: Map<string, PlacedMarker>;
}): void {
  const { map, listings, locale, groupLabel, selectedId, onSelect, markers } = options;
  const coordinates = coordinatesFor(listings);
  const bounds = new google.maps.LatLngBounds();
  const seen = new Set<string>();

  for (const group of groupMarkers(listings)) {
    const position = new google.maps.LatLng(group.lat, group.lng);
    bounds.extend(position);
    seen.add(group.key);
    const title = markerTitle(group, listings, locale, groupLabel);
    const existing = markers.get(group.key);
    if (existing) {
      existing.group = group;
      existing.marker.setPosition(position);
      existing.marker.setTitle(title);
      applyAppearance(existing, selectedId());
      continue;
    }
    const appearance = markerAppearance(group, selectedId());
    const placed: PlacedMarker = {
      marker: new google.maps.Marker({ map, position, title, icon: appearance.icon }),
      group,
    };
    placed.marker.setLabel(appearance.label);
    placed.marker.setZIndex(appearance.zIndex);
    placed.marker.addListener('click', () => {
      onSelect(nextIdInGroup(placed.group, selectedId()));
    });
    markers.set(group.key, placed);
  }

  for (const [key, placed] of markers) {
    if (!seen.has(key)) {
      placed.marker.setMap(null);
      markers.delete(key);
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
  groupLabel = '{count}',
}: ActivityGoogleMapProps) {
  const containerId = useId().replace(/:/g, '');
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<Map<string, PlacedMarker>>(new Map());
  const groupLabelRef = useRef(groupLabel);
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
  useEffect(() => {
    groupLabelRef.current = groupLabel;
  }, [groupLabel]);

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
          groupLabel: groupLabelRef.current,
          selectedId: () => selectedIdRef.current,
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
      groupLabel,
      selectedId: () => selectedIdRef.current,
      onSelect: (activityId) => onSelectRef.current(activityId),
      markers: markersRef.current,
    });
  }, [groupLabel, listingIds, listings, locale]);

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

    for (const placed of markersRef.current.values()) {
      applyAppearance(placed, selectedId);
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
