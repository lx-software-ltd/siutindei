import { describe, expect, it } from 'vitest';

import { listingFactsLine } from '@/components/sections/listings/listing-card';
import { checkedFactLabels } from '@/lib/activities/listing-facts';
import { DEFAULT_SEARCH_KINDS, kindOption, offeredKinds } from '@/lib/home-wizard/choices';
import { familyFoodFilters } from '@/lib/activities/search-params';

import { buildListing } from '../helpers/listing-fixture';

const cafe = buildListing({
  activity: {
    kind: 'eat',
    facts: { high_chairs: true, kids_menu: false, changing_table: true, room_to_run: false },
  },
  organization: { parentVerified: true },
});

describe('eat pilot', () => {
  it('offers eat only once the build lists it as a pilot with enough places', () => {
    expect(offeredKinds([]).map((kind) => kind.id)).toEqual(['class', 'camp', 'place']);
    expect(offeredKinds(['eat']).map((kind) => kind.id)).toEqual([
      'class',
      'camp',
      'place',
      'eat',
    ]);
    expect(DEFAULT_SEARCH_KINDS).not.toContain('eat');
    expect(kindOption('eat')?.id).toBe('eat');
  });

  it('shows the facts a parent checked on the card, the missing ones too', () => {
    expect(checkedFactLabels('en', cafe)).toEqual([
      'High chairs',
      "No kids' menu",
      'Baby changing table',
      'Little room to run around',
    ]);
    expect(listingFactsLine('en', cafe)).toBe(
      "High chairs · No kids' menu · Baby changing table · Little room to run around",
    );
    expect(listingFactsLine('zh-HK', cafe)).toContain('沒有兒童餐');
    expect(listingFactsLine('en', buildListing({ activity: { kind: 'place' } }))).toBeNull();
  });

  it('keeps only the area for the family-food layer', () => {
    expect(
      familyFoodFilters({
        kind: 'class',
        ageGroupId: '3-5',
        regionId: 'kowloon',
        neighbourhoodId: 'mong-kok',
        activityTypeIds: ['art'],
        textQuery: 'paint',
        free: true,
      }),
    ).toEqual({
      kind: 'eat',
      ageGroupId: null,
      regionId: 'kowloon',
      neighbourhoodId: 'mong-kok',
      activityTypeIds: [],
      textQuery: '',
    });
  });
});
