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

function renderNavbar(locale: 'en' | 'zh-HK' = 'en') {
  const content = getContent(locale);
  return render(
    <SearchProvider>
      <Navbar locale={locale} content={content.navbar} />
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

  it('fits the mark, the search bar, and the language switch in one row', () => {
    pathname.mockReturnValue('/en/search/');
    renderNavbar();

    const banner = screen.getByRole('banner');
    const bar = banner.querySelector('.site-header__bar');
    expect(bar).toHaveClass('flex', 'items-center');
    expect(banner.querySelectorAll('[role="search"]')).toHaveLength(1);
    expect(bar?.querySelector('[role="search"]')).not.toBeNull();
    expect(bar?.querySelector('nav')).not.toBeNull();

    const home = screen.getByRole('link', { name: 'Siu Tin Dei' });
    expect(home.getAttribute('href')).toMatch(/^\/en\/?$/);
    expect(bar).toContainElement(home);
    // Phones drop the wordmark so the search bar gets its width.
    expect(home.querySelector('img[src$="siutindei-wordmark.svg"]')).toHaveClass(
      'hidden',
      'sm:block',
    );
    expect(home.querySelector('img[src$="siutindei-logo-mark.svg"]')).not.toHaveClass(
      'hidden',
    );
  });

  it('does not render a list-your-activity link in English', () => {
    pathname.mockReturnValue('/en/search/');
    renderNavbar('en');

    expect(
      screen.queryByRole('link', { name: 'List your activity' }),
    ).not.toBeInTheDocument();
  });

  it('does not render a list-your-activity link in Traditional Chinese', () => {
    pathname.mockReturnValue('/zh-HK/search/');
    renderNavbar('zh-HK');

    expect(screen.getAllByText('地區').length).toBeGreaterThan(0);
    expect(
      screen.queryByRole('link', { name: '刊登活動' }),
    ).not.toBeInTheDocument();
  });
});
