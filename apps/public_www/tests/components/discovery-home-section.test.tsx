import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DiscoveryHomeSection } from '@/components/sections/discovery/discovery-home-section';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { withChromeCopy } from '../helpers/chrome-copy';
import { clearSearchAreaScopeCacheForTests } from '@/lib/home-wizard/area-scope';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';
import type { SearchFiltersState } from '@/lib/activities/search-params';
import type { ActivityListing } from '@/lib/activities/types';

const KOWLOON_AREA_ID = 'a1111111-1111-1111-1111-111111111102';
const ISLAND_AREA_ID = 'a1111111-1111-1111-1111-111111111101';

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivitySearch: vi.fn(),
}));

import { fetchActivitySearch } from '@/lib/activities/search-client';

function buildListing(
  id = 'act-1',
  areaId = KOWLOON_AREA_ID,
  regionAreaId: string | null = areaId,
): ActivityListing {
  return {
    activity: {
      id,
      name: 'Kowloon art',
      description: null,
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c1111111-1111-1111-1111-111111111101',
      kind: 'class',
      facts: {},
      categoryRootId: 'c1111111-1111-1111-1111-111111111101',
      categoryName: null,
      categoryNameTranslations: {},
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
      id: `loc-${id}`,
      areaId,
      regionAreaId,
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

function renderDiscovery(
  locale: 'en' | 'zh-HK' = 'en',
  filters?: SearchFiltersState,
  hasStaticCatalogue = false,
) {
  const content = getContent(locale);
  render(
    withChromeCopy(
      <SearchProvider initialFilters={filters}>
        <DiscoveryHomeSection
          locale={locale}
          copy={content.discovery}
          hasStaticCatalogue={hasStaticCatalogue}
        />
      </SearchProvider>,
    ),
  );
  return content;
}

describe('DiscoveryHomeSection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
  });

  it('links popular and region titles to filtered search pages', async () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing('act-1'), buildListing('act-2', ISLAND_AREA_ID)],
      nextCursor: null,
    });

    const content = renderDiscovery();

    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: content.discovery.popularTitle }),
        ).toHaveAttribute('href', '/en/search?view=map');
    });

    const regionTitle = `${content.discovery.nearRegionTitle} Kowloon`;
    expect(await screen.findByRole('link', { name: regionTitle })).toHaveAttribute(
      'href',
      '/en/search?region=kowloon&view=map',
    );
    expect(
      screen.getByRole('link', {
        name: `${content.discovery.carousel.seeAllLabel}: ${regionTitle}`,
      }),
    ).toHaveAttribute('href', '/en/search?region=kowloon&view=map');
  });

  it('hides the region carousel when every result is in one region', async () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
    });
    const content = renderDiscovery();

    expect(
      await screen.findByRole('link', { name: content.discovery.popularTitle }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: /Activities in Kowloon/ }),
    ).not.toBeInTheDocument();
  });

  it('names one open neighbourhood and skips the repeated region row', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing('act-1', ISLAND_AREA_ID)],
      nextCursor: null,
    });
    const content = renderDiscovery();

    expect(
      await screen.findByRole('link', {
        name: 'Popular activities in Stanley',
      }),
    ).toHaveAttribute('href', '/en/search?view=map');
    expect(
      screen.queryByRole('link', {
        name: `${content.discovery.nearRegionTitle} Hong Kong Island`,
      }),
    ).not.toBeInTheDocument();
  });

  it('names the open neighbourhood in traditional chinese', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing('act-1', ISLAND_AREA_ID)],
      nextCursor: null,
    });
    renderDiscovery('zh-HK');

    expect(await screen.findByRole('link', { name: '赤柱熱門活動' })).toBeInTheDocument();
  });

  it('names whole regions and keeps a separate row for each', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon,islands';
    clearSearchAreaScopeCacheForTests();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [
        buildListing('act-1', KOWLOON_AREA_ID),
        buildListing('act-2', 'a1111111-1111-1111-1111-111111111104'),
      ],
      nextCursor: null,
    });
    const content = renderDiscovery();

    expect(
      await screen.findByRole('link', {
        name: 'Popular activities in Kowloon and Islands',
      }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('link', {
        name: `${content.discovery.nearRegionTitle} Kowloon`,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: `${content.discovery.nearRegionTitle} Islands`,
      }),
    ).toBeInTheDocument();
  });

  it('names a partly open region by its neighbourhood', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon,southern-stanley';
    clearSearchAreaScopeCacheForTests();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [
        buildListing('act-1', KOWLOON_AREA_ID),
        buildListing('act-2', ISLAND_AREA_ID),
      ],
      nextCursor: null,
    });
    const content = renderDiscovery();

    expect(
      await screen.findByRole('link', {
        name: 'Popular activities in Stanley and Kowloon',
      }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('link', {
        name: `${content.discovery.nearRegionTitle} Kowloon`,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: `${content.discovery.nearRegionTitle} Stanley`,
      }),
    ).toBeInTheDocument();
  });

  it('uses the open-areas heading when more than three neighbourhoods are open', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'yau-tsim-mong';
    clearSearchAreaScopeCacheForTests();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
    });
    const content = renderDiscovery();

    expect(
      await screen.findByRole('link', {
        name: content.discovery.popularOpenAreasTitle,
      }),
    ).toBeInTheDocument();
  });

  it('keeps the region name when a row has more than three neighbourhoods', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'yau-tsim-mong,islands';
    clearSearchAreaScopeCacheForTests();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [
        buildListing('act-1', KOWLOON_AREA_ID),
        buildListing('act-2', 'a1111111-1111-1111-1111-111111111104'),
      ],
      nextCursor: null,
    });
    const content = renderDiscovery();

    expect(
      await screen.findByRole('link', {
        name: content.discovery.popularOpenAreasTitle,
      }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('link', {
        name: `${content.discovery.nearRegionTitle} Kowloon`,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', {
        name: `${content.discovery.nearRegionTitle} our open areas`,
      }),
    ).not.toBeInTheDocument();
  });

  it('uses the searched place in the heading', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon,islands';
    clearSearchAreaScopeCacheForTests();
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
    });
    renderDiscovery('en', { ...DEFAULT_SEARCH_FILTERS, regionId: 'kowloon' });

    expect(
      await screen.findByRole('link', { name: 'Popular activities in Kowloon' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', {
        name: 'Popular activities in Kowloon and Islands',
      }),
    ).not.toBeInTheDocument();
  });

  it('groups neighbourhood locations that omit the region id', async () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [
        buildListing('act-1', '4800fff7-4d9b-54df-b2a6-144788bd4a33', null),
        buildListing('act-2', '8e20eb5e-f30a-5b98-b60c-6c9b4b4a81e3', null),
        buildListing('act-3', KOWLOON_AREA_ID),
      ],
      nextCursor: null,
    });
    const content = renderDiscovery();

    expect(
      await screen.findByRole('link', {
        name: `${content.discovery.nearRegionTitle} Hong Kong Island`,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: `${content.discovery.nearRegionTitle} Kowloon`,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: content.discovery.nearRegionTitle }),
    ).not.toBeInTheDocument();
  });

  it('shows the search error when the page has no static catalogue', async () => {
    vi.mocked(fetchActivitySearch).mockRejectedValue(new Error('offline'));
    const content = renderDiscovery();

    expect(await screen.findByText(content.discovery.errorLabel)).toBeInTheDocument();
  });

  it('stays silent on a search error when the page links to the static catalogue', async () => {
    vi.mocked(fetchActivitySearch).mockRejectedValue(new Error('offline'));
    const content = renderDiscovery('en', undefined, true);

    await waitFor(() => {
      expect(fetchActivitySearch).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(
        screen.queryByRole('link', { name: content.discovery.popularTitle }),
      ).not.toBeInTheDocument();
    });
    expect(screen.queryByText(content.discovery.errorLabel)).not.toBeInTheDocument();
  });

  it('says no areas are open when the scope matches nothing', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'atlantis';
    clearSearchAreaScopeCacheForTests();
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [],
      nextCursor: null,
    });
    vi.mocked(fetchActivitySearch).mockClear();
    const content = renderDiscovery();

    expect(await screen.findByRole('status')).toHaveTextContent(
      content.discovery.noAreasOpenLabel,
    );
    expect(fetchActivitySearch).not.toHaveBeenCalled();
    expect(
      screen.queryByRole('link', { name: content.discovery.popularTitle }),
    ).not.toBeInTheDocument();
  });
});
