import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DiscoveryHomeSection } from '@/components/sections/discovery/discovery-home-section';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { withChromeCopy } from '../helpers/chrome-copy';
import type { ActivityListing } from '@/lib/activities/types';

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivitySearch: vi.fn(),
}));

import { fetchActivitySearch } from '@/lib/activities/search-client';

function buildListing(): ActivityListing {
  return {
    activity: {
      id: 'act-1',
      name: 'Kowloon art',
      description: null,
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c1111111-1111-1111-1111-111111111101',
    },
    organization: {
      id: 'org-1',
      name: 'Studio',
      description: null,
      nameTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
    },
    location: {
      id: 'loc-1',
      areaId: 'a1111111-1111-1111-1111-111111111102',
      regionAreaId: 'a1111111-1111-1111-1111-111111111102',
      address: null,
      lat: null,
      lng: null,
    },
    pricing: {
      pricingType: 'per_class',
      amount: 100,
      currency: 'hkd',
      sessionsCount: null,
      freeTrialClassOffered: false,
    },
    schedule: {
      scheduleType: 'weekly',
      weeklyEntries: [],
      languages: ['en'],
    },
  };
}

describe('DiscoveryHomeSection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('links popular and region titles to filtered search pages', async () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
    });

    const content = getContent('en');
    render(
      withChromeCopy(
        <SearchProvider>
          <DiscoveryHomeSection locale="en" copy={content.discovery} />
        </SearchProvider>,
      ),
    );

    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: content.discovery.popularTitle }),
        ).toHaveAttribute('href', '/en/search?age=3-6&view=map');
    });

    const regionTitle = `${content.discovery.nearRegionTitle} Kowloon`;
    expect(await screen.findByRole('link', { name: regionTitle })).toHaveAttribute(
      'href',
      '/en/search?age=3-6&region=kowloon&view=map',
    );
    expect(
      screen.getByRole('link', {
        name: `${content.discovery.carousel.seeAllLabel}: ${regionTitle}`,
      }),
    ).toHaveAttribute('href', '/en/search?age=3-6&region=kowloon&view=map');
  });
});
