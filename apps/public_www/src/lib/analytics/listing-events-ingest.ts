import { getSearchConfig } from '@/lib/site-config';

export type ListingEventType =
  | 'search'
  | 'listing_view'
  | 'cta_tap'
  | 'lead_relayed';

export interface ListingEventPayload {
  readonly event_type: ListingEventType;
  readonly location_id?: string;
  readonly activity_id?: string;
  readonly client_event_id?: string;
}

function newClientEventId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function ingestListingEvents(
  events: readonly ListingEventPayload[],
): Promise<void> {
  if (typeof window === 'undefined' || events.length === 0) {
    return;
  }

  const config = getSearchConfig();
  if (config.stagingSearchDataEnabled || !config.apiBaseUrl) {
    return;
  }

  const url = new URL('/v1/listing-events', config.apiBaseUrl);
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  };
  if (config.apiKey) {
    headers['x-api-key'] = config.apiKey;
  }
  if (config.attestationToken) {
    headers['x-device-attestation'] = config.attestationToken;
  }

  const body = {
    events: events.map((event) => ({
      event_type: event.event_type,
      source: 'public_www',
      ...(event.location_id ? { location_id: event.location_id } : {}),
      ...(event.activity_id ? { activity_id: event.activity_id } : {}),
      client_event_id: event.client_event_id ?? newClientEventId(),
    })),
  };

  try {
    await fetch(url.toString(), {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      keepalive: true,
    });
  } catch {
    // First-party ingest must never break listing UX.
  }
}
