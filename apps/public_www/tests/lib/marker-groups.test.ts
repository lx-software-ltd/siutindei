import { describe, expect, it } from 'vitest';

import { groupMarkers, markerIconSrc, nextIdInGroup } from '@/lib/google-maps/marker-groups';

import { buildListing } from '../helpers/listing-fixture';

describe('groupMarkers', () => {
  it('groups venues within about ten metres and skips listings without coordinates', () => {
    const groups = groupMarkers([
      buildListing({ activity: { id: 'a' }, location: { lat: 22.31931, lng: 114.16941 } }),
      buildListing({ activity: { id: 'b' }, location: { lat: 22.31929, lng: 114.16939 } }),
      buildListing({ activity: { id: 'c' }, location: { lat: 22.3, lng: 114.2 } }),
      buildListing({ activity: { id: 'd' }, location: { lat: null, lng: null } }),
    ]);

    expect(groups.map((group) => group.ids)).toEqual([['a', 'b'], ['c']]);
    expect(markerIconSrc(groups[0], false)).toBe('/images/markers/group.svg');
    expect(markerIconSrc(groups[1], true)).toMatch(/^\/images\/markers\/[a-z-]+-selected\.svg$/);
  });

  it('cycles through the activities that share a pin', () => {
    const [group] = groupMarkers([
      buildListing({ activity: { id: 'a' } }),
      buildListing({ activity: { id: 'b' } }),
    ]);

    expect(nextIdInGroup(group, null)).toBe('a');
    expect(nextIdInGroup(group, 'a')).toBe('b');
    expect(nextIdInGroup(group, 'b')).toBe('a');
  });
});
