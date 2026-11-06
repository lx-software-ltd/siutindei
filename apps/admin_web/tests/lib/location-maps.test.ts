import { describe, expect, it } from 'vitest';

import {
  appleMapsPinUrl,
  buildAppleMapsUrl,
  buildGoogleMapsUrl,
  coordinateFromPosition,
  coordinatesChanged,
  formatMapCoordinate,
  googleMapsPinUrl,
  locationCoordinates,
  locationPinHint,
  nextOpenedCoordinates,
  pinMoveDelay,
  TYPED_PIN_DELAY_MS,
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

describe('formatMapCoordinate', () => {
  it('keeps six decimal places and drops trailing zeros', () => {
    expect(formatMapCoordinate(22.279000000000004)).toBe('22.279');
    expect(formatMapCoordinate(22.28)).toBe('22.28');
    expect(formatMapCoordinate(114)).toBe('114');
  });
});

describe('coordinateFromPosition', () => {
  it('reads a LatLng with methods or a literal', () => {
    expect(coordinateFromPosition({ lat: () => 22.278, lng: () => 114.175 })).toEqual({
      lat: 22.278,
      lng: 114.175,
    });
    expect(coordinateFromPosition({ lat: 22.278, lng: 114.175 })).toEqual({
      lat: 22.278,
      lng: 114.175,
    });
  });

  it('returns null for a missing position', () => {
    expect(coordinateFromPosition(null)).toBeNull();
    expect(coordinateFromPosition({ lat: 'north', lng: 114 })).toBeNull();
  });
});

describe('locationCoordinates', () => {
  it('reads the editor fields when both are in range', () => {
    expect(locationCoordinates({ lat: '22.278', lng: '114.175' })).toEqual({
      lat: 22.278,
      lng: 114.175,
    });
    expect(locationCoordinates({ lat: '', lng: '114.175' })).toBeNull();
  });
});

describe('pinMoveDelay', () => {
  it('leaves a pin that is already on the coordinate', () => {
    expect(pinMoveDelay({ lat: 22.279, lng: 114.176 }, { lat: 22.279, lng: 114.176 })).toBeNull();
    expect(
      pinMoveDelay({ lat: 22.2790004, lng: 114.176 }, { lat: 22.279, lng: 114.176 })
    ).toBeNull();
  });

  it('waits before following a typed coordinate', () => {
    expect(pinMoveDelay({ lat: 22.278, lng: 114.175 }, { lat: 22.2, lng: 114.175 })).toBe(
      TYPED_PIN_DELAY_MS
    );
    expect(pinMoveDelay(null, { lat: 22.2, lng: 114.175 })).toBe(TYPED_PIN_DELAY_MS);
  });

  it('moves immediately when asked', () => {
    expect(
      pinMoveDelay({ lat: 22.278, lng: 114.175 }, { lat: 22.5, lng: 114.175 }, true)
    ).toBe(0);
  });
});

describe('nextOpenedCoordinates', () => {
  const saved = {
    lat: '22.278',
    lng: '114.175',
    address: '123 Test Street',
    area_id: 'area-1',
  };

  it('remembers the placement once the opened record is in the form', () => {
    const blank = { lat: '', lng: '', address: '', area_id: '' };
    expect(nextOpenedCoordinates(null, 'loc-1', saved, blank)).toBeNull();
    const opened = nextOpenedCoordinates(null, 'loc-1', saved, saved);
    expect(opened).toEqual({ key: 'loc-1', ...saved });
    expect(nextOpenedCoordinates(opened, 'loc-1', saved, saved)).toBe(opened);
  });

  it('keeps the opened placement while the fields change', () => {
    const opened = { key: 'loc-1', ...saved };
    expect(
      nextOpenedCoordinates(opened, 'loc-1', saved, { ...saved, lat: '22.5' })
    ).toBe(opened);
    expect(
      nextOpenedCoordinates(opened, 'loc-1', saved, {
        ...saved,
        address: '999 Other Road',
      })
    ).toBe(opened);
    expect(coordinatesChanged({ lat: '22.5', lng: '114.175' }, opened)).toBe(true);
    expect(coordinatesChanged({ lat: '22.2780', lng: '114.175000' }, opened)).toBe(false);
    expect(coordinatesChanged(saved, opened)).toBe(false);
  });

  it('adopts placement after a save updates the record and the form', () => {
    const opened = { key: 'loc-1', ...saved };
    const savedNext = {
      lat: '22.5',
      lng: '114.176',
      address: '123 Test Street',
      area_id: 'area-1',
    };
    expect(
      nextOpenedCoordinates(opened, 'loc-1', savedNext, { ...savedNext, lng: '114.175' })
    ).toBe(opened);
    expect(nextOpenedCoordinates(opened, 'loc-1', savedNext, savedNext)).toEqual({
      key: 'loc-1',
      ...savedNext,
    });
  });

  it('uses an empty placement for a new location after the form clears', () => {
    const previous = { key: 'loc-1', ...saved };
    const blank = { lat: '', lng: '', address: '', area_id: '' };
    expect(nextOpenedCoordinates(previous, 'draft', null, saved)).toBe(previous);
    const draft = nextOpenedCoordinates(previous, 'draft', null, blank);
    expect(draft).toEqual({ key: 'draft', ...blank });
    expect(
      nextOpenedCoordinates(draft, 'draft', null, { ...blank, lat: '22.2' })
    ).toBe(draft);
  });

  it('clears the baseline when the editor closes', () => {
    const opened = { key: 'loc-1', ...saved };
    expect(nextOpenedCoordinates(opened, null, saved, saved)).toBeNull();
  });
});

describe('locationPinHint', () => {
  it('stays quiet when the pin can be placed', () => {
    expect(locationPinHint('22.278', '114.175', false)).toBeNull();
  });

  it('asks for both coordinates while the fields are editable', () => {
    expect(locationPinHint('', '', false)).toBe(
      'Enter latitude and longitude to place the pin.'
    );
    expect(locationPinHint('', '114.175', false)).toBe(
      'Enter both latitude and longitude to place the pin.'
    );
    expect(locationPinHint('91', '114.175', false)).toBe(
      'Latitude must be from -90 to 90 and longitude from -180 to 180.'
    );
  });

  it('does not ask a locked editor to type', () => {
    expect(locationPinHint('', '', true)).toBe(
      'This location has no latitude or longitude.'
    );
    expect(locationPinHint('91', '114.175', true)).toBe(
      'Latitude or longitude is not a valid coordinate.'
    );
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
