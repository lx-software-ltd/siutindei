import { describe, expect, it } from 'vitest';

import {
  locationDisplayName,
  locationListLabel,
} from '@/lib/location-label';

describe('locationDisplayName', () => {
  it('uses the venue name when one is set', () => {
    expect(
      locationDisplayName(
        { name: ' Harbour Hall ', address: '1 Name Road' },
        'loc-1'
      )
    ).toBe('Harbour Hall');
  });

  it('uses the address when the name is empty', () => {
    expect(
      locationDisplayName({ name: '  ', address: '1 Name Road' }, 'loc-1')
    ).toBe('1 Name Road');
    expect(
      locationDisplayName({ name: null, address: '1 Name Road' }, 'loc-1')
    ).toBe('1 Name Road');
  });

  it('uses the caller fallback when the name and address are empty', () => {
    expect(locationDisplayName({ name: '', address: null }, 'loc-1')).toBe(
      'loc-1'
    );
    expect(locationDisplayName({ address: '  ' }, '')).toBe('');
  });
});

describe('locationListLabel', () => {
  const venues = [
    { name: ' Main Hall ', address: '1 Name Road' },
    { name: 'Main Hall', address: '2 Name Road' },
    { name: 'Side Hall', address: '3 Name Road' },
  ];

  it('adds the address when the same name is used twice', () => {
    expect(locationListLabel(venues[0], venues, 'loc-1')).toBe(
      'Main Hall · 1 Name Road'
    );
    expect(locationListLabel(venues[1], venues, 'loc-2')).toBe(
      'Main Hall · 2 Name Road'
    );
  });

  it('leaves a name that is used once', () => {
    expect(locationListLabel(venues[2], venues, 'loc-3')).toBe('Side Hall');
  });

  it('marks a closed venue', () => {
    const venues = [
      { name: 'Main Hall', address: '1 Name Road', status: 'temporarily_closed' },
      { name: 'Side Hall', address: '2 Name Road', status: 'permanently_closed' },
      { name: 'Open Hall', address: '3 Name Road', status: 'open' },
    ];
    expect(locationListLabel(venues[0], venues)).toBe(
      'Main Hall · Temporarily Closed'
    );
    expect(locationListLabel(venues[1], venues)).toBe(
      'Side Hall · Permanently Closed'
    );
    expect(locationListLabel(venues[2], venues)).toBe('Open Hall');
  });

  it('does not repeat a name that is also the address', () => {
    const shared = [
      { name: 'Main Hall', address: 'Main Hall' },
      { name: 'Main Hall', address: '' },
    ];
    expect(locationListLabel(shared[0], shared)).toBe('Main Hall');
    expect(locationListLabel(shared[1], shared, 'loc-2')).toBe('Main Hall');
  });
});
