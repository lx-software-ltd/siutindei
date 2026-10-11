export interface CatalogMapLocation {
  id: string;
  address?: string | null;
  area_name?: string | null;
  lat?: number | null;
  lng?: number | null;
}

export interface CatalogMapOrg {
  id: string;
  name: string;
  map_locations?: CatalogMapLocation[] | null;
}

export interface CatalogMapPin {
  id: string;
  orgName: string;
  address: string;
  areaName: string;
  lat: number;
  lng: number;
  mapsUrl: string;
}

export function googleMapsPinUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
}

function hasPin(location: CatalogMapLocation): boolean {
  return (
    typeof location.lat === 'number' &&
    Number.isFinite(location.lat) &&
    typeof location.lng === 'number' &&
    Number.isFinite(location.lng)
  );
}

export function pinsForOrganizations(
  items: readonly CatalogMapOrg[]
): CatalogMapPin[] {
  const pins: CatalogMapPin[] = [];
  for (const item of items) {
    for (const location of item.map_locations ?? []) {
      if (!hasPin(location) || location.lat == null || location.lng == null) {
        continue;
      }
      pins.push({
        id: location.id,
        orgName: item.name,
        address: location.address?.trim() ?? '',
        areaName: location.area_name?.trim() ?? '',
        lat: location.lat,
        lng: location.lng,
        mapsUrl: googleMapsPinUrl(location.lat, location.lng),
      });
    }
  }
  return pins;
}

export function organizationsWithoutMapPins(
  items: readonly CatalogMapOrg[]
): number {
  return items.filter(
    (item) => !(item.map_locations ?? []).some((location) => hasPin(location))
  ).length;
}
