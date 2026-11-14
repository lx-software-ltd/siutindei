import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SearchResultsPage } from '@/components/pages/search-results-page';
import { OfferedKinds } from '@/components/shared/offered-kinds';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { homeWizardChoices } from '@/lib/home-wizard/choices';
import { withChromeCopy } from '../helpers/chrome-copy';
import { fetchActivitySearch } from '@/lib/activities/search-client';
import { clearSearchAreaScopeCacheForTests } from '@/lib/home-wizard/area-scope';
import type { ActivityListing } from '@/lib/activities/types';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';

const push = vi.hoisted(() => vi.fn());
const replace = vi.hoisted(() => vi.fn());
const mapsEnabled = vi.hoisted(() => ({ value: true }));
const currentSearchParams = vi.hoisted(() => ({
  value: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push,
    replace,
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

/** The filter row, which carries the view switch and sorting on phones. */
function phoneToolbar(): HTMLElement {
  const toolbar = document.querySelector<HTMLElement>('.search-toolbar');
  expect(toolbar).not.toBeNull();
  return toolbar as HTMLElement;
}

/** The row under the filters, which carries them from iPad portrait up. */
function wideSummary(): HTMLElement {
  const summary = document.querySelector<HTMLElement>('.search-results-summary');
  expect(summary).not.toBeNull();
  return summary as HTMLElement;
}

function renderPage(pilotKindIds: readonly string[] = []) {
  const copy = getContent('en').searchPage;
  render(
    withChromeCopy(
      <OfferedKinds pilotKindIds={pilotKindIds}>
        <SearchProvider>
          <SearchResultsPage locale="en" copy={copy} />
        </SearchProvider>
      </OfferedKinds>,
    ),
  );
  return copy;
}

describe('SearchResultsPage', () => {
  beforeEach(() => {
    push.mockClear();
    replace.mockClear();
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
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

  it('hides the name search field and the count until the total arrives', async () => {
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

  it('opens the map by default with a List and Map switch', async () => {
    const copy = renderPage();

    const groups = await screen.findAllByRole('group', { name: copy.viewToggleLabel });
    expect(groups).toHaveLength(2);
    for (const group of groups) {
      expect(group).toHaveClass('search-view-toggle');
      expect(
        within(group).getByRole('button', { name: copy.mapViewLabel }),
      ).toHaveAttribute('aria-pressed', 'true');
    }

    fireEvent.click(
      within(wideSummary()).getByRole('button', { name: copy.listViewLabel }),
    );
    expect(push).toHaveBeenCalledWith(expect.stringContaining('view=list'));
  });

  it('moves the view switch into the filter row on phones', async () => {
    const copy = renderPage();
    await screen.findAllByRole('group', { name: copy.viewToggleLabel });

    const phoneSwitch = within(phoneToolbar()).getByRole('group', {
      name: copy.viewToggleLabel,
    });
    expect(phoneSwitch.parentElement).toHaveClass('md:hidden', 'shrink-0');
    const wideSwitch = within(wideSummary()).getByRole('group', {
      name: copy.viewToggleLabel,
    });
    expect(wideSwitch.parentElement).toHaveClass('max-md:hidden');

    fireEvent.click(
      within(phoneSwitch).getByRole('button', { name: copy.listViewLabel }),
    );
    expect(push).toHaveBeenCalledWith(expect.stringContaining('view=list'));
  });

  it('gives phones the whole screen for the map', async () => {
    const copy = renderPage();
    await screen.findByRole('application', { name: copy.mapAriaLabel });

    const page = document.querySelector('.search-page');
    expect(page).toHaveClass('search-page--map');
    expect(
      document.querySelector('.search-map-split-layout')?.closest('.search-page__results'),
    ).not.toBeNull();
    // Sorting does not change which pins show, so the map view leaves it out.
    expect(
      within(phoneToolbar()).queryByRole('combobox', { name: copy.sortLabel }),
    ).toBeNull();
  });

  it('lets the list page scroll', async () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    const copy = renderPage();
    await screen.findAllByRole('group', { name: copy.viewToggleLabel });

    expect(document.querySelector('.search-page')).not.toHaveClass('search-page--map');
  });

  it('switches from the list to the map when view=list', async () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    const copy = renderPage();

    const maps = await screen.findAllByRole('button', { name: copy.mapViewLabel });
    expect(maps).toHaveLength(2);
    for (const map of maps) {
      expect(map).toHaveAttribute('aria-pressed', 'false');
    }

    fireEvent.click(maps[0]);
    expect(push).toHaveBeenCalledWith(expect.stringContaining('view=map'));
  });

  it('shows the total, active filters, and removes one filter', async () => {
    currentSearchParams.value = new URLSearchParams('view=list&age=3-5&free=1&day=weekend');
    vi.mocked(fetchActivitySearch).mockResolvedValue({
      items: [buildListing()],
      nextCursor: null,
      total: 12,
    });
    const copy = renderPage();

    const count = await screen.findByText('12 activities');
    expect(count).toHaveAttribute('role', 'status');
    // Phones read the count out and keep the space for results.
    expect(count).toHaveClass('max-md:sr-only');
    expect(fetchActivitySearch).toHaveBeenCalledWith(
      expect.objectContaining({
        includeTotal: true,
        pricingType: 'free',
        daysOfWeekHkt: [0, 6],
      }),
      expect.anything(),
    );
    const filters = screen.getByRole('list', { name: copy.activeFiltersLabel });
    fireEvent.click(
      within(filters).getByRole('button', { name: 'Remove filter: Weekend' }),
    );
    expect(replace).toHaveBeenLastCalledWith('/en/search/?age=3-5&free=1&view=list');

    fireEvent.click(within(filters).getByRole('button', { name: copy.clearFiltersLabel }));
    expect(replace).toHaveBeenLastCalledWith('/en/search/?view=list');
  });

  it('shows phones only the name search among the applied filters', async () => {
    currentSearchParams.value = new URLSearchParams('view=list&q=pottery&age=3-5&free=1');
    const copy = renderPage();

    const filters = await screen.findByRole('list', { name: copy.activeFiltersLabel });
    const hiddenOnPhones = (name: string) =>
      within(filters)
        .getByRole('button', { name })
        .closest('li')
        ?.classList.contains('max-md:hidden');

    const query = within(filters).getByRole('button', { name: /pottery/ });
    expect(query.closest('li')).not.toHaveClass('max-md:hidden');
    expect(hiddenOnPhones('Remove filter: Free')).toBe(true);
    expect(hiddenOnPhones(copy.clearFiltersLabel)).toBe(true);
    expect(wideSummary()).toHaveClass('pt-2');
  });

  it('leaves no gap under the filter row on phones without a name search', async () => {
    currentSearchParams.value = new URLSearchParams('view=list&age=3-5');
    const copy = renderPage();
    await screen.findByRole('list', { name: copy.activeFiltersLabel });

    expect(wideSummary()).not.toHaveClass('pt-2');
    expect(wideSummary()).toHaveClass('md:pt-3');
  });

  it('labels a search without an age as all ages', async () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    const copy = renderPage();

    const filters = await screen.findByRole('list', { name: copy.activeFiltersLabel });
    expect(within(filters).getByText(copy.allAgesLabel)).toBeInTheDocument();
    expect(within(filters).queryByRole('button')).not.toBeInTheDocument();
  });

  it('sorts by lowest price', async () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    const copy = renderPage();

    const sorts = await screen.findAllByRole('combobox', { name: copy.sortLabel });
    expect(sorts).toHaveLength(2);
    fireEvent.change(within(wideSummary()).getByRole('combobox', { name: copy.sortLabel }), {
      target: { value: 'price' },
    });
    expect(replace).toHaveBeenLastCalledWith('/en/search/?sort=price&view=list');
  });

  it('sorts from the filter row on phones, where each choice names itself', async () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    const copy = renderPage();
    await screen.findAllByRole('combobox', { name: copy.sortLabel });

    const sort = within(phoneToolbar()).getByRole('combobox', { name: copy.sortLabel });
    expect([...sort.querySelectorAll('option')].map((option) => option.textContent)).toEqual([
      'Sort: Day and time',
      'Sort: Lowest price',
    ]);
    const wide = within(wideSummary()).getByRole('combobox', { name: copy.sortLabel });
    expect([...wide.querySelectorAll('option')].map((option) => option.textContent)).toEqual([
      copy.sortTimeLabel,
      copy.sortPriceLabel,
    ]);

    fireEvent.change(sort, { target: { value: 'price' } });
    expect(replace).toHaveBeenLastCalledWith('/en/search/?sort=price&view=list');
  });

  it('remembers the search for the activity page back link', async () => {
    currentSearchParams.value = new URLSearchParams('view=list&age=3-5');
    renderPage();

    await waitFor(() => {
      expect(window.sessionStorage.getItem('siutindei.lastSearchHref')).toBe(
        '/en/search/?age=3-5&view=list',
      );
    });
  });

  it('does not refetch when only the view query changes', async () => {
    const copy = getContent('en').searchPage;
    function Tree() {
      return withChromeCopy(
        <SearchProvider>
          <SearchResultsPage locale="en" copy={copy} />
        </SearchProvider>,
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
        screen.getAllByRole('button', { name: copy.mapViewLabel }).length,
      ).toBeGreaterThan(0);
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

    const card = await waitFor(() => {
      const element = document.querySelector<HTMLElement>('.search-map-split-layout__card');
      expect(element).not.toBeNull();
      return element as HTMLElement;
    });
    expect(within(card).getByRole('link', { name: /Kowloon art/ })).toHaveAttribute(
      'href',
      '/en/activity?id=act-1',
    );
    expect(document.querySelector('.search-map-split-layout__list')).not.toBeNull();
    expect(document.querySelector('.search-map-split-layout')?.parentElement).toHaveClass(
      'lg:mx-auto',
      'lg:max-w-7xl',
      'lg:px-8',
      'lg:pt-4',
    );
  });

  it('adds family-friendly food pins beside the results once eat is offered', async () => {
    const cafe: ActivityListing = {
      ...buildListing(),
      activity: {
        ...buildListing().activity,
        id: 'eat-1',
        name: 'Harbour Cafe',
        kind: 'eat',
        facts: { high_chairs: true, kids_menu: false },
      },
      organization: { ...buildListing().organization, id: 'org-2', parentVerified: true },
    };
    vi.mocked(fetchActivitySearch).mockImplementation(async (params) => ({
      items: params.kinds?.includes('eat') ? [cafe] : [buildListing()],
      nextCursor: null,
    }));
    currentSearchParams.value = new URLSearchParams('age=3-5&region=kowloon');
    const copy = renderPage(['eat']);

    const toggle = await screen.findByRole('button', { name: copy.familyFoodLabel });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    const results = await screen.findByRole('region', { name: copy.resultsLabel });
    await within(results).findByText('Kowloon art');
    expect(within(results).queryByText('Harbour Cafe')).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(await within(results).findByText('Harbour Cafe')).toBeInTheDocument();
    expect(within(results).getByText("High chairs · No kids' menu")).toBeInTheDocument();
    expect(within(results).getByText('Kowloon art')).toBeInTheDocument();
    const foodRequest = vi
      .mocked(fetchActivitySearch)
      .mock.calls.map(([params]) => params)
      .find((params) => params.kinds?.includes('eat'));
    expect(foodRequest).toMatchObject({ kinds: ['eat'] });
    expect(foodRequest).not.toHaveProperty('ageMin');

    fireEvent.click(toggle);
    await waitFor(() =>
      expect(within(results).queryByText('Harbour Cafe')).not.toBeInTheDocument(),
    );
  });

  it('does not offer family-friendly food before the pilot has enough places', async () => {
    const copy = renderPage();
    await screen.findByRole('application', { name: copy.mapAriaLabel });
    expect(screen.queryByRole('button', { name: copy.familyFoodLabel })).not.toBeInTheDocument();
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

  it('searches the neighbourhood named in the query', async () => {
    currentSearchParams.value = new URLSearchParams(
      'region=kowloon&neighbourhood=yau-tsim-mong-mong-kok&age=3-5',
    );
    renderPage();

    await waitFor(() => {
      expect(fetchActivitySearch).toHaveBeenCalledWith(
        expect.objectContaining({
          areaId: '817456a3-b9ae-5b02-9e2b-f88caafe4f72',
        }),
        expect.anything(),
      );
    });
  });

  it('pushes search after a successful fetch when consent is granted', async () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    currentSearchParams.value = new URLSearchParams(
      'q=pottery&region=kowloon&age=3-5&types=art',
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
        category_id: 'c1111111-1111-1111-1111-111111111304',
      });
    });
  });

  it('replaces an out-of-scope area link and explains the change', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon';
    clearSearchAreaScopeCacheForTests();
    currentSearchParams.value = new URLSearchParams('region=islands');
    vi.mocked(fetchActivitySearch).mockClear();
    const copy = getContent('en').searchPage;
    function Tree() {
      return withChromeCopy(
        <SearchProvider>
          <SearchResultsPage locale="en" copy={copy} />
        </SearchProvider>,
      );
    }
    const { rerender } = render(<Tree />);

    expect(await screen.findByText(copy.areaAdjustedLabel)).toHaveAttribute('role', 'status');
    expect(replace).toHaveBeenCalledWith(
      '/en/search/?region=kowloon&view=map',
    );
    await waitFor(() => {
      expect(fetchActivitySearch).toHaveBeenCalledTimes(1);
    });
    const kowloon = homeWizardChoices.regions.find(
      (region) => region.id === 'kowloon',
    );
    const requested = vi.mocked(fetchActivitySearch).mock.calls[0]?.[0];
    expect(requested?.areaId).toBe(kowloon?.areaId);

    currentSearchParams.value = new URLSearchParams(
      'region=kowloon&view=map',
    );
    await act(async () => {
      rerender(<Tree />);
    });
    expect(screen.getByText(copy.areaAdjustedLabel)).toBeInTheDocument();
    expect(fetchActivitySearch).toHaveBeenCalledTimes(1);

    currentSearchParams.value = new URLSearchParams(
      'age=6-11&region=kowloon&view=map',
    );
    await act(async () => {
      rerender(<Tree />);
    });
    expect(screen.queryByText(copy.areaAdjustedLabel)).not.toBeInTheDocument();
  });

  it('does not rewrite a search that names no area', async () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    currentSearchParams.value = new URLSearchParams('age=3-5');
    vi.mocked(fetchActivitySearch).mockClear();
    const copy = renderPage();

    await waitFor(() => {
      expect(fetchActivitySearch).toHaveBeenCalled();
    });
    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByText(copy.areaAdjustedLabel)).not.toBeInTheDocument();
    expect(vi.mocked(fetchActivitySearch).mock.calls[0]?.[0]?.areaId).toBeUndefined();
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
    expect(screen.queryByText(copy.emptyLabel)).not.toBeInTheDocument();
    expect(window.dataLayer).toEqual([]);
  });
});
