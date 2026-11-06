export function parseCoordinate(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function locationCoordinates(location: {
  lat?: unknown;
  lng?: unknown;
}): { lat: number; lng: number } | null {
  const lat = parseCoordinate(location.lat);
  const lng = parseCoordinate(location.lng);
  if (lat == null || lng == null) {
    return null;
  }
  return { lat, lng };
}

export function googleMapsPinUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps?q=${lat},${lng}&z=17`;
}

export function appleMapsPinUrl(lat: number, lng: number): string {
  return `https://maps.apple.com/?ll=${lat},${lng}&q=${lat},${lng}`;
}

function encodedAddressQuery(location: {
  address?: string | null;
}): string | null {
  const query = location.address?.trim();
  return query ? encodeURIComponent(query) : null;
}

export function buildGoogleMapsUrl(location: {
  address?: string | null;
  lat?: unknown;
  lng?: unknown;
}): string | null {
  const pin = locationCoordinates(location);
  if (pin) {
    return googleMapsPinUrl(pin.lat, pin.lng);
  }
  const query = encodedAddressQuery(location);
  if (!query) {
    return null;
  }
  return `https://www.google.com/maps/search/?api=1&query=${query}`;
}

export function buildAppleMapsUrl(location: {
  address?: string | null;
  lat?: unknown;
  lng?: unknown;
}): string | null {
  const pin = locationCoordinates(location);
  if (pin) {
    return appleMapsPinUrl(pin.lat, pin.lng);
  }
  const query = encodedAddressQuery(location);
  if (!query) {
    return null;
  }
  return `https://maps.apple.com/?q=${query}`;
}
