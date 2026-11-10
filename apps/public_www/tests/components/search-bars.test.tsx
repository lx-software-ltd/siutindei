import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { HeroSearchBar } from '@/components/sections/hero/hero-search-bar';
import { SearchBarCompact } from '@/components/sections/search/search-bar-compact';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { clearSearchAreaScopeCacheForTests } from '@/lib/home-wizard/area-scope';

const push = vi.hoisted(() => vi.fn());

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push,
  }),
}));

function renderBars() {
  const labels = getContent('en').navbar.searchBar;
  render(
    <SearchProvider>
      <HeroSearchBar locale="en" labels={labels} />
      <SearchBarCompact locale="en" labels={labels} />
    </SearchProvider>,
  );
}

describe('search bars with one open region', () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
    push.mockClear();
  });

  it('names the open place, maps to it, and searches without storing it', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    renderBars();

    expect(screen.getAllByText('Stanley').length).toBeGreaterThan(0);
    expect(
      screen.getByRole('link', { name: 'Show activities on map for: Stanley' }),
    ).toHaveAttribute(
      'href',
      '/en/search?age=3-6&region=hong_kong_island&neighbourhood=southern-stanley&view=map',
    );

    const summaries = screen
      .getAllByRole('button', { name: 'Search activities' })
      .map((button) => button.textContent ?? '');
    expect(summaries.some((text) => text.includes('Stanley') && text.includes('3–6'))).toBe(
      true,
    );

    const searchButtons = screen
      .getAllByRole('button', { name: 'Search activities' })
      .filter((button) => button.textContent?.includes('⌕'));
    fireEvent.click(searchButtons[0]);
    expect(push).toHaveBeenCalledWith('/en/search/?age=3-6&view=map');
  });
});
