import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Navbar } from '@/components/sections/navbar';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { HERO_SEARCH_SENTINEL_ATTR } from '@/lib/home-header-reveal';

const pathname = vi.hoisted(() => vi.fn(() => '/en/'));

vi.mock('next/navigation', () => ({
  usePathname: () => pathname(),
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

type ObserveFn = (target: Element) => void;

let observerCallback:
  | ((entries: Pick<IntersectionObserverEntry, 'isIntersecting'>[]) => void)
  | null = null;

class MockIntersectionObserver {
  readonly observe: ObserveFn = vi.fn();
  readonly disconnect = vi.fn();
  readonly unobserve = vi.fn();
  readonly takeRecords = () => [];
  readonly root = null;
  readonly rootMargin = '';
  readonly thresholds: readonly number[] = [];

  constructor(
    callback: (
      entries: Pick<IntersectionObserverEntry, 'isIntersecting'>[],
    ) => void,
  ) {
    observerCallback = callback;
  }
}

function emitIntersection(isIntersecting: boolean) {
  observerCallback?.([{ isIntersecting }]);
}

function renderNavbar() {
  const content = getContent('en');
  return render(
    <SearchProvider>
      <Navbar locale="en" content={content.navbar} />
    </SearchProvider>,
  );
}

describe('Navbar', () => {
  beforeEach(() => {
    observerCallback = null;
    pathname.mockReturnValue('/en/');
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
    const sentinel = document.createElement('div');
    sentinel.setAttribute(HERO_SEARCH_SENTINEL_ATTR, '');
    document.body.append(sentinel);
  });

  afterEach(() => {
    document.body.replaceChildren();
    vi.unstubAllGlobals();
  });

  it('keeps the home header hidden until the hero search leaves view', async () => {
    renderNavbar();

    const header = document.querySelector('header');
    expect(header).toHaveClass('site-header--home-reveal');
    expect(header).not.toHaveClass('is-revealed');
    expect(header).toHaveAttribute('inert');
    expect(header).toHaveAttribute('aria-hidden', 'true');

    emitIntersection(false);

    await waitFor(() => {
      expect(header).toHaveClass('is-revealed');
      expect(header).not.toHaveAttribute('inert');
      expect(header).not.toHaveAttribute('aria-hidden');
    });

    emitIntersection(true);

    await waitFor(() => {
      expect(header).not.toHaveClass('is-revealed');
      expect(header).toHaveAttribute('inert');
    });
  });

  it('keeps the header visible on inner pages', () => {
    pathname.mockReturnValue('/en/search/');
    renderNavbar();

    expect(screen.getByRole('banner')).toHaveClass('sticky');
    expect(screen.getByRole('banner')).not.toHaveClass(
      'site-header--home-reveal',
    );
    expect(screen.getByRole('banner')).not.toHaveAttribute('inert');
  });

  it('does not render a list-your-activity link', () => {
    pathname.mockReturnValue('/en/search/');
    renderNavbar();

    expect(
      screen.queryByRole('link', { name: 'List your activity' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: '刊登活動' }),
    ).not.toBeInTheDocument();
  });
});
