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

function inRange(value: number, min: number, max: number): boolean {
  return value >= min && value <= max;
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
  if (!inRange(lat, -90, 90) || !inRange(lng, -180, 180)) {
    return null;
  }
  return { lat, lng };
}

export function formatMapCoordinate(value: number): string {
  return value.toFixed(6).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
}

/** How long a typed coordinate waits before the pin follows it. */
export const TYPED_PIN_DELAY_MS = 400;

export function coordinatesMatch(
  left: { lat: number; lng: number },
  right: { lat: number; lng: number }
): boolean {
  return (
    Math.abs(left.lat - right.lat) < 1e-6 &&
    Math.abs(left.lng - right.lng) < 1e-6
  );
}

/**
 * Null when the pin is already on `next`, including a drag that just
 * landed. A typed change waits so each keystroke does not recenter.
 */
export function pinMoveDelay(
  current: { lat: number; lng: number } | null,
  next: { lat: number; lng: number }
): number | null {
  if (current && coordinatesMatch(current, next)) {
    return null;
  }
  return TYPED_PIN_DELAY_MS;
}

function coordinateBlank(value: unknown): boolean {
  if (value == null) {
    return true;
  }
  return typeof value === 'string' && value.trim() === '';
}

/** Sentence shown when the editor cannot place a pin. Null when it can. */
export function locationPinHint(
  lat: unknown,
  lng: unknown,
  readOnly: boolean
): string | null {
  if (locationCoordinates({ lat, lng })) {
    return null;
  }
  const latBlank = coordinateBlank(lat);
  const lngBlank = coordinateBlank(lng);
  if (readOnly) {
    if (latBlank && lngBlank) {
      return 'This location has no latitude or longitude.';
    }
    return 'Latitude or longitude is not a valid coordinate.';
  }
  if (latBlank && lngBlank) {
    return 'Enter latitude and longitude to place the pin.';
  }
  if (latBlank || lngBlank) {
    return 'Enter both latitude and longitude to place the pin.';
  }
  return 'Latitude must be from -90 to 90 and longitude from -180 to 180.';
}

export function coordinateFromPosition(
  position: unknown,
): { lat: number; lng: number } | null {
  if (!position || typeof position !== 'object') {
    return null;
  }
  const point = position as { lat?: unknown; lng?: unknown };
  const read = (value: unknown): unknown =>
    typeof value === 'function' ? (value as () => unknown)() : value;
  const lat = read(point.lat);
  const lng = read(point.lng);
  if (typeof lat !== 'number' || typeof lng !== 'number') {
    return null;
  }
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null;
  }
  return { lat, lng };
}

export function googleMapsPinUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
}

export function appleMapsPinUrl(
  lat: number,
  lng: number,
  label?: string | null,
): string {
  const trimmed = label?.trim();
  const query = trimmed ? encodeURIComponent(trimmed) : `${lat},${lng}`;
  return `https://maps.apple.com/?ll=${lat},${lng}&q=${query}`;
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
    return appleMapsPinUrl(pin.lat, pin.lng, location.address);
  }
  const query = encodedAddressQuery(location);
  if (!query) {
    return null;
  }
  return `https://maps.apple.com/?q=${query}`;
}
