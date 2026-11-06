import { describe, expect, it } from 'vitest';

import {
  appleMapsPinUrl,
  buildAppleMapsUrl,
  buildGoogleMapsUrl,
  googleMapsPinUrl,
} from '@/lib/location-maps';

const GOOGLE_PIN = 'https://www.google.com/maps/search/?api=1&query=22.278,114.175';
const ADDRESS_SEARCH =
  'https://www.google.com/maps/search/?api=1&query=123%20Test%20Street';

describe('googleMapsPinUrl', () => {
  it('drops a pin at the coordinates', () => {
    expect(googleMapsPinUrl(22.278, 114.175)).toBe(GOOGLE_PIN);
  });
});

describe('appleMapsPinUrl', () => {
  it('uses the address as the pin label', () => {
    expect(appleMapsPinUrl(22.278, 114.175, '123 Test Street')).toBe(
      'https://maps.apple.com/?ll=22.278,114.175&q=123%20Test%20Street'
    );
  });

  it('uses the coordinates as the label when the address is blank', () => {
    expect(appleMapsPinUrl(22.278, 114.175, '  ')).toBe(
      'https://maps.apple.com/?ll=22.278,114.175&q=22.278,114.175'
    );
  });
});

describe('buildGoogleMapsUrl', () => {
  it('pins numeric coordinates instead of searching the address', () => {
    expect(
      buildGoogleMapsUrl({
        address: '123 Test Street',
        lat: 22.278,
        lng: 114.175,
      })
    ).toBe(GOOGLE_PIN);
  });

  it('pins decimal strings from JSON serialization', () => {
    expect(
      buildGoogleMapsUrl({
        address: '123 Test Street',
        lat: '22.278000',
        lng: '114.175000',
      })
    ).toBe(GOOGLE_PIN);
  });

  it('searches the address when coordinates are missing', () => {
    expect(buildGoogleMapsUrl({ address: '123 Test Street' })).toBe(
      ADDRESS_SEARCH
    );
  });

  it('searches the address when a coordinate is outside its range', () => {
    expect(
      buildGoogleMapsUrl({
        address: '123 Test Street',
        lat: 91,
        lng: 114.175,
      })
    ).toBe(ADDRESS_SEARCH);
    expect(
      buildGoogleMapsUrl({
        address: '123 Test Street',
        lat: 22.278,
        lng: 181,
      })
    ).toBe(ADDRESS_SEARCH);
  });

  it('searches the address when a coordinate is not a number', () => {
    expect(
      buildGoogleMapsUrl({
        address: '123 Test Street',
        lat: 'north',
        lng: '114.175',
      })
    ).toBe(ADDRESS_SEARCH);
  });

  it('returns null when there is no pin and no address', () => {
    expect(buildGoogleMapsUrl({})).toBeNull();
    expect(buildGoogleMapsUrl({ address: '  ', lat: null, lng: null })).toBeNull();
  });
});

describe('buildAppleMapsUrl', () => {
  it('pins the coordinates and labels them with the address', () => {
    expect(
      buildAppleMapsUrl({
        address: '123 Test Street',
        lat: 22.278,
        lng: 114.175,
      })
    ).toBe('https://maps.apple.com/?ll=22.278,114.175&q=123%20Test%20Street');
  });

  it('searches the address when coordinates are missing', () => {
    expect(buildAppleMapsUrl({ address: '123 Test Street' })).toBe(
      'https://maps.apple.com/?q=123%20Test%20Street'
    );
  });
});
