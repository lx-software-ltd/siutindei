import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  AGE_ICON_SRC,
  ALL_HONG_KONG_ICON_SRC,
  DEFAULT_ACTIVITY_ICON_SRC,
  KIND_ICON_SRC,
  REGION_ICON_SRC,
  REGION_ROW_ORDER,
  activityTypeIdForCategory,
  iconSrcForActivity,
  iconSrcForListing,
  iconSrcForAge,
  iconSrcForKind,
  iconSrcForRegion,
  WEEKEND_ICON_SRC,
} from '@/lib/home-wizard/choice-icons';
import { homeWizardChoices } from '@/lib/home-wizard/choices';

describe('choice icons', () => {
  it('maps every activity type to a category illustration', () => {
    for (const type of homeWizardChoices.activityTypes) {
      expect(iconSrcForActivity(type.id)).toMatch(
        /^\/images\/categories\/.+\.svg$/,
      );
    }
  });

  it('maps listing category ids to activity-type icons', () => {
    for (const type of homeWizardChoices.activityTypes) {
      expect(activityTypeIdForCategory(type.categoryId)).toBe(type.id);
      expect(
        iconSrcForListing({ kind: 'class', categoryId: 'leaf', categoryRootId: type.categoryId }),
      ).toBe(iconSrcForActivity(type.id));
    }
    expect(activityTypeIdForCategory(null)).toBe('');
    expect(activityTypeIdForCategory('unknown')).toBe('');
    expect(iconSrcForListing({ kind: 'class', categoryId: null, categoryRootId: null })).toBe(
      DEFAULT_ACTIVITY_ICON_SRC,
    );
    expect(iconSrcForListing({ kind: 'place', categoryId: 'park', categoryRootId: 'places' })).toBe(
      KIND_ICON_SRC.place,
    );
  });

  it('maps every age group to the original age PNGs', () => {
    expect(Object.keys(AGE_ICON_SRC)).toEqual(
      homeWizardChoices.ageGroups.map((group) => group.id),
    );
    expect(AGE_ICON_SRC).toEqual({
      '0-1': '/images/ages/baby.png',
      '1-2': '/images/ages/baby.png',
      '3-5': '/images/ages/toddler.png',
      '6-11': '/images/ages/child.png',
      '12-18': '/images/ages/child.png',
    });
    for (const group of homeWizardChoices.ageGroups) {
      expect(iconSrcForAge(group.id)).toMatch(/^\/images\/ages\/.+\.png$/);
    }
  });

  it('gives every kind and the weekend preset an illustration with a map marker', () => {
    for (const kind of homeWizardChoices.kinds) {
      expect(iconSrcForKind(kind.id)).toBe(KIND_ICON_SRC[kind.id]);
    }
    expect(iconSrcForKind('unknown')).toBe(DEFAULT_ACTIVITY_ICON_SRC);
    const sources = [
      ...Object.values(KIND_ICON_SRC),
      ...homeWizardChoices.activityTypes.map((type) => iconSrcForActivity(type.id)),
      WEEKEND_ICON_SRC,
      DEFAULT_ACTIVITY_ICON_SRC,
    ];
    for (const src of sources) {
      for (const path of [src, src.replace('/images/categories/', '/images/markers/')]) {
        expect(existsSync(resolve(__dirname, '../../public', path.slice(1)))).toBe(true);
      }
    }
  });

  it('lists regions from Hong Kong Island through the islands', () => {
    expect([...REGION_ROW_ORDER]).toEqual([
      'hong_kong_island',
      'kowloon',
      'new_territories',
      'islands',
    ]);
    expect([...REGION_ROW_ORDER].sort()).toEqual(
      homeWizardChoices.regions.map((region) => region.id).sort(),
    );
    for (const region of homeWizardChoices.regions) {
      expect(iconSrcForRegion(region.id)).toBe(REGION_ICON_SRC[region.id]);
    }
    expect(ALL_HONG_KONG_ICON_SRC).toBe('/images/flags/hong-kong.svg');
  });

  it('stores region icons as outline-only SVGs', () => {
    for (const src of Object.values(REGION_ICON_SRC)) {
      const file = resolve(__dirname, '../../public', src.slice(1));
      const svg = readFileSync(file, 'utf8');
      expect(svg).toContain('<path');
      expect(svg).toContain('fill="none"');
      expect(svg).not.toMatch(/fill="#[0-9A-Fa-f]/);
    }
  });
});
