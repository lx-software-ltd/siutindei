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
    expect(document.querySelector('.hero-scope-sign')).not.toBeInTheDocument();
    expect(document.querySelector('.hero-scope-strike')).not.toBeInTheDocument();
  });

  it('strikes Hong Kong and points at the open plates', () => {
    const content = getContent('en');
    const signs = [
      { id: 'southern-stanley', en: 'Stanley', zhHK: '赤柱' },
      { id: 'southern-repulse-bay', en: 'Repulse Bay', zhHK: '淺水灣' },
      { id: 'southern-shek-o', en: 'Shek O', zhHK: '石澳' },
    ];

    render(
      <SearchProvider>
        <SmallWorldHero
          locale="en"
          bubbleIds={bubbleIds}
          copy={content.smallWorld}
          searchBarLabels={content.navbar.searchBar}
          scopeSigns={signs}
        />
      </SearchProvider>,
    );

    const strike = document.querySelector('.hero-scope-strike');
    expect(strike).toHaveTextContent('Hong Kong');
    expect(strike).toHaveAttribute('aria-hidden', 'true');
    expect(
      document.querySelector('.small-world-hero h1 + p .sr-only'),
    ).toHaveTextContent('Stanley, Repulse Bay and Shek O');
    const plates = document.querySelectorAll('.hero-scope-sign');
    expect(plates).toHaveLength(3);
    expect(plates[0]).toHaveAttribute(
      'src',
      '/images/scope-signs/southern-stanley.webp',
    );
    expect(plates[2]).toHaveClass('hero-scope-sign--extra');
    expect(plates[2]).toHaveAttribute('data-scope-sign-target', '');
    expect(
      document.querySelector('img[src="/images/ui/scope-arrow.svg"]'),
    ).toBeInTheDocument();
    expect(document.querySelector('.hero-scope-arrow')).toBeInTheDocument();
    expect(document.querySelectorAll('.small-world-bubble')).toHaveLength(5);
  });

  it('reads the open places in Chinese', () => {
    const content = getContent('zh-HK');

    render(
      <SearchProvider>
        <SmallWorldHero
          locale="zh-HK"
          bubbleIds={bubbleIds}
          copy={content.smallWorld}
          searchBarLabels={content.navbar.searchBar}
          scopeSigns={[
            { id: 'southern-stanley', en: 'Stanley', zhHK: '赤柱' },
            { id: 'southern-repulse-bay', en: 'Repulse Bay', zhHK: '淺水灣' },
          ]}
        />
      </SearchProvider>,
    );

    expect(document.querySelector('.hero-scope-strike')).toHaveTextContent('香港');
    expect(
      document.querySelector('.small-world-hero h1 + p .sr-only'),
    ).toHaveTextContent('赤柱及淺水灣');
  });
});
