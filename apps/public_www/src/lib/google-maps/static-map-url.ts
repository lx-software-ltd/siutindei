import type { MapCoordinate } from './coordinates';

const STATIC_MAP_SIZE = {
  card: { width: 600, height: 200 },
  detail: { width: 800, height: 400 },
} as const;

export type StaticMapVariant = keyof typeof STATIC_MAP_SIZE;

function encodeMarker(coordinate: MapCoordinate): string {
  return `color:0x3a5ba0|${coordinate.lat},${coordinate.lng}`;
}

export function buildStaticMapUrl(params: {
  readonly apiKey: string;
  readonly coordinate: MapCoordinate;
  readonly variant: StaticMapVariant;
  readonly zoom?: number;
  readonly scale?: 1 | 2;
}): string {
  const size = STATIC_MAP_SIZE[params.variant];
  const url = new URL('https://maps.googleapis.com/maps/api/staticmap');
  url.searchParams.set('center', `${params.coordinate.lat},${params.coordinate.lng}`);
  url.searchParams.set('zoom', String(params.zoom ?? 14));
  url.searchParams.set('size', `${size.width}x${size.height}`);
  url.searchParams.set('scale', String(params.scale ?? 2));
  url.searchParams.set('maptype', 'roadmap');
  url.searchParams.append('markers', encodeMarker(params.coordinate));
  url.searchParams.set('key', params.apiKey);
  return url.toString();
}
