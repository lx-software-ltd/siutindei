import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  AGE_ICON_SRC,
  ALL_HONG_KONG_ICON_SRC,
  DEFAULT_ACTIVITY_ICON_SRC,
  REGION_ICON_SRC,
  REGION_ROW_ORDER,
  activityTypeIdForCategory,
  iconSrcForActivity,
  iconSrcForActivityCategory,
  iconSrcForAge,
  iconSrcForRegion,
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
      expect(iconSrcForActivityCategory(type.categoryId)).toBe(
        iconSrcForActivity(type.id),
      );
    }
    expect(activityTypeIdForCategory(null)).toBe('early-years');
    expect(activityTypeIdForCategory('unknown')).toBe('early-years');
    expect(iconSrcForActivityCategory(null)).toBe(DEFAULT_ACTIVITY_ICON_SRC);
  });

  it('maps every age group to the original age PNGs', () => {
    expect(Object.keys(AGE_ICON_SRC)).toEqual(
      homeWizardChoices.ageGroups.map((group) => group.id),
    );
    expect(AGE_ICON_SRC).toEqual({
      '1-3': '/images/ages/baby.png',
      '3-6': '/images/ages/toddler.png',
      '6-12': '/images/ages/child.png',
    });
    for (const group of homeWizardChoices.ageGroups) {
      expect(iconSrcForAge(group.id)).toMatch(/^\/images\/ages\/.+\.png$/);
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
