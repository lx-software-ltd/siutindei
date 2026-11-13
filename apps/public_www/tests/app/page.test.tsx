import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DiscoveryHomePage } from '@/components/pages/discovery-home-page';
import { PageLayout } from '@/components/shared/page-layout';
import { getContent } from '@/content';
import { HOME_ACTIVITY_LINK_LIMIT } from '@/components/sections/discovery/home-catalogue-links';
import { clearCatalogueCacheForTests } from '@/lib/activities/catalogue-snapshot';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';

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
  const originalWhatsapp = process.env.NEXT_PUBLIC_WHATSAPP_URL;

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    window.localStorage.clear();
    delete window.dataLayer;
    if (originalWhatsapp === undefined) {
      delete process.env.NEXT_PUBLIC_WHATSAPP_URL;
    } else {
      process.env.NEXT_PUBLIC_WHATSAPP_URL = originalWhatsapp;
    }
  });

  it('renders discovery chrome with search and carousel headings', () => {
    process.env.NEXT_PUBLIC_WHATSAPP_URL = 'https://wa.me/85200000000';
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    window.dataLayer = [];
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
    expect(screen.getByText(content.hostCta.description)).toBeInTheDocument();
    const partner = screen.getByRole('link', { name: content.hostCta.buttonLabel });
    expect(partner).toHaveClass('bg-brand-500', 'text-ink-900');
    expect(partner).toHaveAttribute('href', 'https://wa.me/85200000000');
    expect(partner).toHaveAttribute('target', '_blank');
    fireEvent.click(partner);
    expect(window.dataLayer).toEqual([
      { event: 'generate_lead', lead_type: 'whatsapp_partner' },
    ]);
    expect(screen.getByRole('heading', { level: 2, name: content.features.title })).toBeInTheDocument();
    expect(screen.getByText(content.pages.about.intro[0])).toBeInTheDocument();
    for (const section of content.pages.about.sections) {
      const heading = screen.queryByRole('heading', {
        level: 3,
        name: section.heading,
      });
      if (section.id === 'write-to-me') {
        expect(heading).not.toBeInTheDocument();
      } else {
        expect(heading).toBeInTheDocument();
        expect(screen.getByText(section.paragraphs[0])).toBeInTheDocument();
      }
    }
    expect(document.querySelector('.hero-scope-sign')).not.toBeInTheDocument();
    expect(screen.getByText(content.discovery.pageTitle)).toBeVisible();
  });

  it('links to the pre-rendered activity pages without the search API', () => {
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'true');
    vi.stubEnv('PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH', '');
    clearCatalogueCacheForTests();
    const content = getContent('en');

    try {
      render(
        <PageLayout locale="en" navbarContent={content.navbar} footerContent={content.footer}>
          <DiscoveryHomePage locale="en" content={content} />
        </PageLayout>,
      );
    } finally {
      vi.unstubAllEnvs();
      clearCatalogueCacheForTests();
    }

    const activityLinks = Array.from(
      document.querySelectorAll('#home-catalogue-heading ~ ul a[href^="/en/activity/"]'),
    );
    expect(activityLinks).toHaveLength(HOME_ACTIVITY_LINK_LIMIT);
    expect(document.querySelector('a[href^="/en/activities/early-years"]')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /See all \d+ activities/ }).getAttribute('href')).toMatch(
      /^\/en\/activities\/?$/,
    );
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
    expect(screen.getByText(content.smallWorld.subtitle)).toBeInTheDocument();
    expect(document.querySelector('.small-world-hero__copy')).toHaveAttribute(
      'data-scope-signs',
      '1',
    );
  });
});
