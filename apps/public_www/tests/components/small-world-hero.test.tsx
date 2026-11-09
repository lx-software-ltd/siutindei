import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SmallWorldHero } from '@/components/sections/hero/small-world-hero';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import {
  BUBBLE_BUILD_SEED,
  pickBubbleIdsForSeed,
} from '@/lib/small-world/kawaii-bubbles';

const bubbleIds = pickBubbleIdsForSeed(BUBBLE_BUILD_SEED);

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe('SmallWorldHero', () => {
  it('renders the brand story and search bar', () => {
    const content = getContent('en');

    render(
      <SearchProvider>
        <SmallWorldHero
          locale="en"
          bubbleIds={bubbleIds}
          copy={content.smallWorld}
          searchBarLabels={content.navbar.searchBar}
        />
      </SearchProvider>,
    );

    expect(
      screen.getByRole('heading', { level: 1, name: content.smallWorld.title }),
    ).toBeInTheDocument();
    expect(
      document.querySelector(
        'img[src="/images/brand/siutindei-logo-stacked.svg"]',
      ),
    ).toBeInTheDocument();
    expect(
      document.querySelector(
        'img[src="/images/brand/siutindei-logo-mark.svg"]',
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(content.smallWorld.subtitle),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/little explorers/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('Parent-Verified programmes'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('Curated across Hong Kong'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('Clear schedules and pricing'),
    ).not.toBeInTheDocument();

    expect(
      screen.getAllByRole('button', {
        name: content.navbar.searchBar.search,
      }).length,
    ).toBeGreaterThan(0);
    expect(
      document.querySelector('[data-hero-search-sentinel]'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: content.smallWorld.navigator.buttonLabel,
      }),
    ).toBeInTheDocument();
  });

  it('shows a random set of kawaii bubbles after mount', async () => {
    const content = getContent('en');

    render(
      <SearchProvider>
        <SmallWorldHero
          locale="en"
          bubbleIds={bubbleIds}
          copy={content.smallWorld}
          searchBarLabels={content.navbar.searchBar}
        />
      </SearchProvider>,
    );

    await waitFor(() => {
      expect(
        document.querySelectorAll('.small-world-bubble'),
      ).toHaveLength(6);
    });
    for (const bubble of document.querySelectorAll('.small-world-bubble')) {
      expect(bubble.getAttribute('fetchpriority')).toBe('low');
    }
    expect(
      document.querySelectorAll('.max-lg\\:hidden'),
    ).toHaveLength(3);
  });
});
