import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SearchResultsPage } from '@/components/pages/search-results-page';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { fetchActivitySearch } from '@/lib/activities/search-client';
import type { ActivityListing } from '@/lib/activities/types';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';

const push = vi.hoisted(() => vi.fn());
const mapsEnabled = vi.hoisted(() => ({ value: true }));
const currentSearchParams = vi.hoisted(() => ({
  value: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push,
  }),
  useSearchParams: () => currentSearchParams.value,
}));

vi.mock('@/lib/google-maps/config', () => ({
  isGoogleMapsEnabled: () => mapsEnabled.value,
}));

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivitySearch: vi.fn().mockResolvedValue({
    items: [],
    nextCursor: null,
  }),
}));

vi.mock('@/components/shared/maps/activity-google-map', () => ({
  ActivityGoogleMap: ({ ariaLabel }: { ariaLabel: string }) => (
    <div role="application" aria-label={ariaLabel} />
  ),
}));

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
      lat: 22.3193,
      lng: 114.1694,
    },
    pricing: {
      pricingType: 'per_class',
      amount: 180,
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

function renderPage() {
  const copy = getContent('en').searchPage;
  render(
    <SearchProvider>
      <SearchResultsPage locale="en" copy={copy} />
    </SearchProvider>,
  );
  return copy;
}

describe('SearchResultsPage', () => {
  beforeEach(() => {
    push.mockClear();
    mapsEnabled.value = true;
    currentSearchParams.value = new URLSearchParams();
    window.localStorage.clear();
    window.dataLayer = [];
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [],
      nextCursor: null,
    });
  });

  afterEach(() => {
    window.localStorage.clear();
    delete window.dataLayer;
  });

  it('hides the name search field and activity count', async () => {
    const copy = renderPage();

    await waitFor(() => {
      expect(screen.getAllByText(copy.emptyLabel).length).toBeGreaterThan(0);
    });

    expect(
      screen.queryByPlaceholderText('Search by name or organization'),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(screen.queryByText(/^\d+ activities$/)).not.toBeInTheDocument();
  });

  it('shows the map canvas while the first search request is in flight', async () => {
    vi.mocked(fetchActivitySearch).mockReturnValue(new Promise(() => {}));
    const copy = renderPage();

    expect(
      await screen.findByRole('application', { name: copy.mapAriaLabel }),
    ).toBeInTheDocument();
  });

  it('opens the map by default and overlays a list toggle', async () => {
    const copy = renderPage();

    const toggle = await screen.findByRole('button', {
      name: copy.listViewLabel,
    });
    expect(toggle.querySelector('img')).toHaveAttribute(
      'src',
      '/images/ui/list.svg',
    );
    expect(toggle).toHaveClass('search-view-toggle', 'fixed', 'rounded-full', 'bg-white');
    expect(toggle.parentElement).toBe(document.body);

    fireEvent.click(toggle);
    expect(push).toHaveBeenCalledWith(expect.stringContaining('view=list'));
  });

  it('overlays a map toggle on the list when view=list', async () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    const copy = renderPage();

    const toggle = await screen.findByRole('button', {
      name: copy.mapViewLabel,
    });
    expect(toggle.querySelector('img')).toHaveAttribute(
      'src',
      '/images/ui/map.svg',
    );

    fireEvent.click(toggle);
    expect(push).toHaveBeenCalledWith(expect.stringContaining('view=map'));
  });

  it('does not refetch when only the view query changes', async () => {
    const copy = getContent('en').searchPage;
    function Tree() {
      return (
        <SearchProvider>
          <SearchResultsPage locale="en" copy={copy} />
        </SearchProvider>
      );
    }

    vi.mocked(fetchActivitySearch).mockClear();
    const { rerender } = render(<Tree />);

    await waitFor(() => {
      expect(fetchActivitySearch).toHaveBeenCalled();
    });
    const callsAfterFirstLoad =
      vi.mocked(fetchActivitySearch).mock.calls.length;

    currentSearchParams.value = new URLSearchParams('view=list');
    rerender(<Tree />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: copy.mapViewLabel }),
      ).toBeInTheDocument();
    });
    expect(vi.mocked(fetchActivitySearch).mock.calls.length).toBe(
      callsAfterFirstLoad,
    );
  });

  it('auto-selects a filtered pin and links the map card to activity details', async () => {
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
    });
    renderPage();

    const summaryLink = await screen.findByRole('link', {
      name: /Kowloon art/,
    });
    expect(summaryLink).toHaveAttribute('href', '/en/activity?id=act-1');
    expect(
      document.querySelector('.search-map-split-layout__list'),
    ).toHaveClass('hidden', 'lg:block');
  });

  it('hides the view toggle when maps are disabled', async () => {
    mapsEnabled.value = false;
    const copy = renderPage();

    await waitFor(() => {
      expect(screen.getByText(copy.emptyLabel)).toBeInTheDocument();
    });

    expect(
      screen.queryByRole('button', { name: copy.mapViewLabel }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: copy.listViewLabel }),
    ).not.toBeInTheDocument();
  });

  it('pushes search after a successful fetch when consent is granted', async () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    currentSearchParams.value = new URLSearchParams(
      'q=pottery&region=kowloon&age=3-6&types=early-years',
    );
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
    });
    renderPage();

    await waitFor(() => {
      expect(window.dataLayer).toContainEqual({
        event: 'search',
        search_term: 'pottery',
        area_id: 'a1111111-1111-1111-1111-111111111102',
        age: 4,
        category_id: 'c1111111-1111-1111-1111-111111111201',
      });
    });
  });

  it('explains results that still use the previous categories', async () => {
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
      categoryMatch: 'legacy_fallback',
    });
    const copy = renderPage();

    expect(await screen.findByText(copy.unsortedCategoryLabel)).toBeTruthy();
  });

  it('does not push search when the fetch fails', async () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    vi.mocked(fetchActivitySearch).mockRejectedValue(new Error('offline'));
    const copy = renderPage();

    await waitFor(() => {
      expect(screen.getByText(copy.errorLabel)).toBeInTheDocument();
    });
    expect(window.dataLayer).toEqual([]);
  });
});
