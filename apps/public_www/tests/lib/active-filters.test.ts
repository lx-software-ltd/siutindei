import { describe, expect, it } from 'vitest';

import { getContent } from '@/content';
import { activeFilters, clearedFilters } from '@/lib/activities/active-filters';
import { DEFAULT_SEARCH_FILTERS, type SearchFiltersState } from '@/lib/activities/search-params';
import { homeWizardChoices } from '@/lib/home-wizard/choices';

const copy = getContent('en').searchPage;

describe('activeFilters', () => {
  it('shows all ages as a fixed chip when no age is chosen', () => {
    const chips = activeFilters('en', DEFAULT_SEARCH_FILTERS, copy);
    expect(chips).toEqual([{ id: 'age', label: copy.allAgesLabel, without: null }]);
  });

  it('lists every filter with the filters left after removing it', () => {
    const type = homeWizardChoices.activityTypes[0];
    const filters: SearchFiltersState = {
      ageGroupId: '3-6',
      regionId: 'kowloon',
      neighbourhoodId: null,
      activityTypeIds: [type.id],
      textQuery: 'swim',
      free: true,
      day: '6',
      language: 'en',
      classPriceMax: 150,
    };

    const chips = activeFilters('en', filters, copy);
    expect(chips.map((chip) => chip.label)).toEqual([
      'Kowloon',
      homeWizardChoices.ageGroups.find((group) => group.id === '3-6')?.labels.en,
      type.labels.en,
      '“swim”',
      copy.freeFilterLabel,
      'Saturday',
      'English',
      'Up to HK$150 a class',
    ]);
    expect(chips.find((chip) => chip.id === 'place')?.without).toMatchObject({
      regionId: null,
      neighbourhoodId: null,
    });
    expect(chips.find((chip) => chip.id === 'day')?.without?.day).toBeNull();
  });

  it('clears everything except the place and sort', () => {
    expect(
      clearedFilters({
        ...DEFAULT_SEARCH_FILTERS,
        regionId: 'kowloon',
        ageGroupId: '3-6',
        free: true,
        sort: 'price',
      }),
    ).toEqual({ ...DEFAULT_SEARCH_FILTERS, regionId: 'kowloon', sort: 'price' });
  });
});
