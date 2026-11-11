import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  SearchMapSplitLayout,
  type SearchMapLoadMore,
} from '@/components/sections/search/search-map-split-layout';
import { getContent } from '@/content';
import type { ActivityListing } from '@/lib/activities/types';

const mapsEnabled = vi.hoisted(() => ({ value: true }));

vi.mock('@/lib/google-maps/config', () => ({
  isGoogleMapsEnabled: () => mapsEnabled.value,
}));

vi.mock('@/components/shared/maps/activity-google-map', () => ({
  ActivityGoogleMap: ({
    ariaLabel,
    onSelect,
  }: {
    ariaLabel: string;
    onSelect: (activityId: string) => void;
  }) => (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={() => onSelect('act-2')}
    >
      Map pins
    </button>
  ),
}));

function buildListing(
  id: string,
  name: string,
  lat: number | null,
): ActivityListing {
  return {
    activity: {
      id,
      name,
      description: null,
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c1111111-1111-1111-1111-111111111101',
    },
    organization: {
      id: `org-${id}`,
      name: 'Studio',
      description: null,
      nameTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
    },
    location: {
      id: `loc-${id}`,
      areaId: 'a1111111-1111-1111-1111-111111111102',
      regionAreaId: 'a1111111-1111-1111-1111-111111111102',
      address: null,
      lat,
      lng: lat === null ? null : 114.1694,
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

const listings: readonly ActivityListing[] = [
  buildListing('act-1', 'Kowloon art', 22.3193),
  buildListing('act-2', 'Harbour music', 22.295),
];

function renderLayout(
  props: Partial<{
    selectedId: string | null;
    isLoading: boolean;
    listings: readonly ActivityListing[];
    onSelect: (activityId: string) => void;
    loadMore: SearchMapLoadMore;
  }> = {},
) {
  const copy = getContent('en').searchPage;
  const onSelect = props.onSelect ?? vi.fn();
  const { container } = render(
    <SearchMapSplitLayout
      locale="en"
      copy={copy}
      listings={props.listings ?? listings}
      selectedId={props.selectedId === undefined ? 'act-1' : props.selectedId}
      onSelect={onSelect}
      isLoading={props.isLoading ?? false}
      loadMore={props.loadMore}
    />,
  );
  return { copy, onSelect, container };
}

describe('SearchMapSplitLayout', () => {
  it('shows the list, the phone card row, and a capped summary card for the selected pin', () => {
    const { copy, container } = renderLayout();

    const list = screen.getByRole('region', { name: copy.resultsLabel });
    expect(list).toHaveClass('search-map-split-layout__list');
    expect(document.querySelector('.search-map-split-layout__sheet')).not.toBeNull();

    const card = document.querySelector('.search-map-split-layout__card');
    expect(card).toHaveClass('md:block', 'lg:hidden', 'short:hidden');

    const summaryLink = within(card as HTMLElement).getByRole('link', { name: /Kowloon art/ });
    expect(summaryLink).toHaveAttribute('href', '/en/activity?id=act-1');
    expect(summaryLink).toHaveTextContent('HK$180 / class');
    expect(summaryLink).toHaveTextContent(copy.viewLabel);

    const enlarge = screen.getByRole('button', { name: copy.enlargeMapLabel });
    expect(enlarge).toHaveClass('hidden', 'lg:inline-flex');
    expect(container.querySelector('[data-hide-whatsapp-fab]')).not.toBeNull();
  });

  it('selects a pin on the map so the cards can open that activity', () => {
    const onSelect = vi.fn();
    const { copy } = renderLayout({ onSelect });

    fireEvent.click(screen.getByRole('button', { name: copy.mapAriaLabel }));
    expect(onSelect).toHaveBeenCalledWith('act-2');
  });

  it('selects from the list and links each row to its activity', () => {
    const onSelect = vi.fn();
    const { copy } = renderLayout({ onSelect });

    const list = screen.getByRole('region', { name: copy.resultsLabel });
    fireEvent.click(within(list).getByRole('button', { name: /Harbour music/ }));
    expect(onSelect).toHaveBeenCalledWith('act-2');
    expect(
      within(list).getByRole('link', { name: `${copy.viewLabel}: Harbour music` }),
    ).toHaveAttribute('href', '/en/activity?id=act-2');
    expect(
      within(list).getByRole('button', { name: /Kowloon art/ }).closest('article'),
    ).toHaveAttribute('aria-current', 'true');
  });

  it('loads more results from inside the list and the card row', () => {
    const onLoadMore = vi.fn();
    const { copy } = renderLayout({
      loadMore: { hasMore: true, isLoadingMore: false, errorMessage: null, onLoadMore },
    });

    const buttons = screen.getAllByRole('button', { name: copy.loadMoreLabel });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[0]);
    fireEvent.click(buttons[1]);
    expect(onLoadMore).toHaveBeenCalledTimes(2);
  });

  it('enlarges the map and reduces back to the split list', () => {
    const { copy } = renderLayout();

    fireEvent.click(screen.getByRole('button', { name: copy.enlargeMapLabel }));

    expect(document.querySelector('.search-map-split-layout--expanded')).not.toBeNull();
    expect(document.querySelector('.search-map-split-layout__card')).not.toHaveClass('lg:hidden');

    const reduce = screen.getByRole('button', { name: copy.reduceMapLabel });
    expect(reduce.querySelector('img')).toHaveAttribute('src', '/images/ui/reduce-map.svg');

    fireEvent.click(reduce);
    expect(document.querySelector('.search-map-split-layout--expanded')).toBeNull();
    expect(screen.getByRole('button', { name: copy.enlargeMapLabel })).toBeInTheDocument();
  });

  it('keeps the cards off the map while results are loading', () => {
    const { copy } = renderLayout({ isLoading: true, selectedId: null });

    expect(screen.getAllByText(copy.loadingMapLabel).length).toBeGreaterThan(0);
    expect(document.querySelector('.search-map-split-layout__card')).toBeNull();
    expect(document.querySelector('.search-map-split-layout__sheet')).toBeNull();
    expect(screen.getByRole('button', { name: copy.mapAriaLabel })).toBeInTheDocument();
  });

  it('mounts the map canvas on the first load before listings arrive', () => {
    const { copy } = renderLayout({
      isLoading: true,
      listings: [],
      selectedId: null,
    });

    expect(screen.getByRole('button', { name: copy.mapAriaLabel })).toBeInTheDocument();
    expect(screen.getAllByText(copy.loadingMapLabel).length).toBeGreaterThan(0);
  });
});
