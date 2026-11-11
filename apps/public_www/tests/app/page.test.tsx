import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DiscoveryHomePage } from '@/components/pages/discovery-home-page';
import { PageLayout } from '@/components/shared/page-layout';
import { getContent } from '@/content';

vi.mock('next/navigation', () => ({
  usePathname: () => '/en/',
  useRouter: () => ({
    push: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivitySearch: vi.fn().mockResolvedValue({ items: [], nextCursor: null }),
}));

describe('DiscoveryHomePage', () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
  });

  it('renders discovery chrome with search and carousel headings', () => {
    const content = getContent('en');

    render(
      <PageLayout
        locale="en"
        navbarContent={content.navbar}
        footerContent={content.footer}
      >
        <DiscoveryHomePage locale="en" content={content} />
      </PageLayout>,
    );

    const header = document.querySelector('header');
    expect(header).toHaveClass('site-header--home-reveal');
    expect(header).not.toHaveClass('is-revealed');
    expect(header).toHaveAttribute('aria-hidden', 'true');

    const homeLink = screen.getByRole('link', {
      name: content.navbar.brand,
      hidden: true,
    });
    expect(
      homeLink.querySelector('img[src="/images/brand/siutindei-logo-mark.svg"]'),
    ).toBeInTheDocument();
    expect(
      homeLink.querySelector('img[src="/images/brand/siutindei-wordmark.svg"]'),
    ).toBeInTheDocument();
    expect(homeLink).not.toHaveTextContent(content.navbar.brand);

    expect(
      screen.getAllByRole('button', { name: content.navbar.searchBar.search })
        .length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole('heading', { level: 1, name: content.smallWorld.title }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: content.smallWorld.navigator.buttonLabel,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Choose a world to explore' }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(content.discovery.popularTitle)).toBeInTheDocument();
    expect(screen.getByText(content.hostCta.title)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: content.hostCta.buttonLabel }),
    ).toHaveClass('bg-brand-500', 'text-ink-900');
    expect(screen.getByRole('heading', { level: 2, name: content.features.title })).toBeInTheDocument();
    expect(document.querySelector('.hero-scope-sign')).not.toBeInTheDocument();
  });

  it('shows the Stanley plate when the scope names Stanley', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    const content = getContent('en');

    render(
      <PageLayout
        locale="en"
        navbarContent={content.navbar}
        footerContent={content.footer}
      >
        <DiscoveryHomePage locale="en" content={content} />
      </PageLayout>,
    );

    expect(
      document.querySelector(
        'img[src="/images/scope-signs/southern-stanley.webp"]',
      ),
    ).toBeInTheDocument();
    expect(document.querySelector('.hero-scope-strike')).toHaveTextContent(
      'Hong Kong',
    );
  });
});
