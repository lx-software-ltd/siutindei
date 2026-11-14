import type { ActivityListing } from '@/lib/activities/types';
import { iconSrcForListing } from '@/lib/home-wizard/choice-icons';

import { listingCoordinate } from './coordinates';

/** Activities whose venues round to the same point (about 10 m) share one pin. */
export interface MarkerGroup {
  readonly key: string;
  readonly lat: number;
  readonly lng: number;
  readonly ids: readonly string[];
  /** The pin icon of the first activity at the place. */
  readonly iconSrc: string;
}

const GROUP_PRECISION = 4;

export function groupMarkers(listings: readonly ActivityListing[]): readonly MarkerGroup[] {
  const groups = new Map<string, { lat: number; lng: number; ids: string[]; iconSrc: string }>();
  for (const listing of listings) {
    const coordinate = listingCoordinate(listing);
    if (!coordinate) {
      continue;
    }
    const key = `${coordinate.lat.toFixed(GROUP_PRECISION)},${coordinate.lng.toFixed(GROUP_PRECISION)}`;
    const group = groups.get(key);
    if (group) {
      if (!group.ids.includes(listing.activity.id)) {
        group.ids.push(listing.activity.id);
      }
      continue;
    }
    groups.set(key, {
      lat: coordinate.lat,
      lng: coordinate.lng,
      ids: [listing.activity.id],
      iconSrc: iconSrcForListing(listing.activity),
    });
  }
  return [...groups].map(([key, group]) => ({ key, ...group }));
}

export function markerIconSrc(group: MarkerGroup, isSelected: boolean): string {
  const suffix = isSelected ? '-selected' : '';
  if (group.ids.length > 1) {
    return `/images/markers/group${suffix}.svg`;
  }
  return group.iconSrc
    .replace('/images/categories/', '/images/markers/')
    .replace(/\.svg$/, `${suffix}.svg`);
}

/** Tapping a shared pin again moves to the next activity at that place. */
export function nextIdInGroup(group: MarkerGroup, selectedId: string | null): string {
  const index = selectedId ? group.ids.indexOf(selectedId) : -1;
  return group.ids[(index + 1) % group.ids.length];
}
