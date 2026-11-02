import type { ActivityListing } from '@/lib/activities/types';

export interface MapCoordinate {
  readonly lat: number;
  readonly lng: number;
}

export const HONG_KONG_CENTER: MapCoordinate = {
  lat: 22.3193,
  lng: 114.1694,
};

export function listingCoordinate(
  listing: ActivityListing,
): MapCoordinate | null {
  const { lat, lng } = listing.location;
  if (lat === null || lng === null) {
    return null;
  }
  return { lat, lng };
}

export function listingsWithCoordinates(
  listings: readonly ActivityListing[],
): readonly ActivityListing[] {
  return listings.filter((listing) => listingCoordinate(listing) !== null);
}

function boundsForCoordinates(
  coordinates: readonly MapCoordinate[],
): { readonly north: number; readonly south: number; readonly east: number; readonly west: number } | null {
  if (coordinates.length === 0) {
    return null;
  }

  let north = coordinates[0].lat;
  let south = coordinates[0].lat;
  let east = coordinates[0].lng;
  let west = coordinates[0].lng;

  for (const point of coordinates.slice(1)) {
    north = Math.max(north, point.lat);
    south = Math.min(south, point.lat);
    east = Math.max(east, point.lng);
    west = Math.min(west, point.lng);
  }

  return { north, south, east, west };
}

export function centerForCoordinates(
  coordinates: readonly MapCoordinate[],
): MapCoordinate {
  const bounds = boundsForCoordinates(coordinates);
  if (!bounds) {
    return HONG_KONG_CENTER;
  }

  return {
    lat: (bounds.north + bounds.south) / 2,
    lng: (bounds.east + bounds.west) / 2,
  };
}
