import { describe, expect, it } from 'vitest';

import { capListingAge } from '@/lib/listing-age';

describe('capListingAge', () => {
  it('stores anything over 18 as 18 and keeps a single age', () => {
    expect(capListingAge(5, 100)).toEqual({ ageMin: 5, ageMax: 18 });
    expect(capListingAge(20, 40)).toEqual({ ageMin: 18, ageMax: 18 });
    expect(capListingAge(5, 5)).toEqual({ ageMin: 5, ageMax: 5 });
  });
});
