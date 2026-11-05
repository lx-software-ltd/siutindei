import { describe, expect, it } from 'vitest';

import { locationDisplayName } from '@/lib/location-label';

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

  it('uses the fallback when the name and address are empty', () => {
    expect(locationDisplayName({ name: '', address: null }, 'loc-1')).toBe(
      'loc-1'
    );
    expect(
      locationDisplayName({ address: '  ', area_id: 'area-1' }, '')
    ).toBe('area-1');
  });
});
