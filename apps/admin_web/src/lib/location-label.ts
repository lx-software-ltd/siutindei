type LocationLabel = {
  name?: string | null;
  address?: string | null;
};

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
  const label = locationDisplayName(location, fallback);
  const name = location.name?.trim();
  if (!name) {
    return label;
  }
  const shared = locations.filter((item) => item.name?.trim() === name);
  if (shared.length < 2) {
    return label;
  }
  const address = location.address?.trim();
  if (!address || address === name) {
    return label;
  }
  return `${name} · ${address}`;
}
