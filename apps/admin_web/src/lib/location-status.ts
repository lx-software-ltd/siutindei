export const LOCATION_STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'temporarily_closed', label: 'Temporarily Closed' },
  { value: 'permanently_closed', label: 'Permanently Closed' },
] as const;

export type LocationStatus = (typeof LOCATION_STATUSES)[number]['value'];

export const DEFAULT_LOCATION_STATUS: LocationStatus = 'open';

export function isLocationStatus(value: unknown): value is LocationStatus {
  return LOCATION_STATUSES.some((item) => item.value === value);
}

export function isLocationClosed(value: unknown): boolean {
  return value === 'temporarily_closed' || value === 'permanently_closed';
}

/** Label for a location status. Unknown values, including organization listing statuses, return null. */
export function locationStatusLabel(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  return LOCATION_STATUSES.find((item) => item.value === value)?.label ?? null;
}
