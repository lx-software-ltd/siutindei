import { isLocationClosed, locationStatusLabel } from './location-status';

type LocationLabel = {
  name?: string | null;
  address?: string | null;
  status?: string | null;
};

function withClosedMark(label: string, location: LocationLabel): string {
  if (!isLocationClosed(location.status)) {
    return label;
  }
  const closed = locationStatusLabel(location.status);
  if (!closed) {
    return label;
  }
  return `${label} · ${closed}`;
}

/** Label shown for a venue: its name, otherwise its address. */
export function locationDisplayName(
  location: LocationLabel,
  fallback = ''
): string {
  const name = location.name?.trim();
  if (name) {
    return name;
  }
  const address = location.address?.trim();
  if (address) {
    return address;
  }
  return fallback;
}

/**
 * List and dropdown label. A name used by more than one venue keeps
 * that venue's address beside it.
 */
export function locationListLabel(
  location: LocationLabel,
  locations: readonly LocationLabel[],
  fallback = ''
): string {
  const label = locationDisplayName(
    { name: location.name, address: location.address },
    fallback
  );
  const name = location.name?.trim();
  if (!name) {
    return withClosedMark(label, location);
  }
  const shared = locations.filter((item) => item.name?.trim() === name);
  if (shared.length < 2) {
    return withClosedMark(label, location);
  }
  const address = location.address?.trim();
  if (!address || address === name) {
    return withClosedMark(label, location);
  }
  return withClosedMark(`${name} · ${address}`, location);
}
