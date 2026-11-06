import { describe, expect, it } from 'vitest';

import {
  appleMapsPinUrl,
  buildAppleMapsUrl,
  buildGoogleMapsUrl,
  googleMapsPinUrl,
} from '@/lib/location-maps';

describe('googleMapsPinUrl', () => {
  it('drops a pin at the coordinates', () => {
    expect(googleMapsPinUrl(22.278, 114.175)).toBe(
      'https://www.google.com/maps?q=22.278,114.175&z=17'
    );
  });
});

describe('appleMapsPinUrl', () => {
  it('centers Apple Maps on the coordinates', () => {
    expect(appleMapsPinUrl(22.278, 114.175)).toBe(
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
    ).toBe('https://www.google.com/maps?q=22.278,114.175&z=17');
  });

  it('pins decimal strings from JSON serialization', () => {
    expect(
      buildGoogleMapsUrl({
        address: '123 Test Street',
        lat: '22.278000',
        lng: '114.175000',
      })
    ).toBe('https://www.google.com/maps?q=22.278,114.175&z=17');
  });

  it('searches the address when coordinates are missing', () => {
    expect(buildGoogleMapsUrl({ address: '123 Test Street' })).toBe(
      'https://www.google.com/maps/search/?api=1&query=123%20Test%20Street'
    );
  });

  it('returns null when there is no pin and no address', () => {
    expect(buildGoogleMapsUrl({})).toBeNull();
    expect(buildGoogleMapsUrl({ address: '  ', lat: null, lng: null })).toBeNull();
  });
});

describe('buildAppleMapsUrl', () => {
  it('pins numeric coordinates instead of searching the address', () => {
    expect(
      buildAppleMapsUrl({
        address: '123 Test Street',
        lat: 22.278,
        lng: 114.175,
      })
    ).toBe('https://maps.apple.com/?ll=22.278,114.175&q=22.278,114.175');
  });

  it('searches the address when coordinates are missing', () => {
    expect(buildAppleMapsUrl({ address: '123 Test Street' })).toBe(
      'https://maps.apple.com/?q=123%20Test%20Street'
    );
  });
});
