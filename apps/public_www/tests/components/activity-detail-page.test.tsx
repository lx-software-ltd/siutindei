import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ActivityDetailPage } from '@/components/pages/activity-detail-page';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { rememberSearchHref } from '@/lib/activities/recent-storage';
import {
  fetchActivityListingById,
  fetchActivitySearch,
} from '@/lib/activities/search-client';
import type { ActivityListing, OrganizationContact } from '@/lib/activities/types';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';

import { withChromeCopy } from '../helpers/chrome-copy';
import { buildListing, buildLocation } from '../helpers/listing-fixture';

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivityListingById: vi.fn(),
  fetchActivitySearch: vi.fn(),
}));

const copy = getContent('en').activityDetail;

const CONTACT: OrganizationContact = {
  website: 'https://studio.example.com',
  email: 'hello@studio.example.com',
  phoneCountryCode: null,
  phoneNumber: null,
  whatsapp: null,
  facebook: null,
  instagram: 'examplestudio',
  tiktok: null,
  twitter: null,
  xiaohongshu: null,
  wechat: null,
};

function fullListing(): ActivityListing {
  return buildListing({
    activity: { ageMin: 3, ageMax: 6, description: 'Paint together.\n\nBring an apron.' },
    organization: {
      parentVerified: true,
      contact: CONTACT,
      rating: { count: 4, averageStars: 4.5 },
      reviews: [],
    },
  });
}

function renderPage(): ReturnType<typeof render> {
  const page: ReactElement = (
    <SearchProvider>
      <ActivityDetailPage locale="en" activityId="act-1" copy={copy} />
    </SearchProvider>
  );
  return render(withChromeCopy(page));
}

describe('ActivityDetailPage', () => {
  const originalWhatsapp = process.env.NEXT_PUBLIC_WHATSAPP_URL;

  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.dataLayer = [];
    process.env.NEXT_PUBLIC_WHATSAPP_URL = 'https://wa.me/85200000000';
    vi.mocked(fetchActivityListingById).mockResolvedValue(buildListing());
    vi.mocked(fetchActivitySearch).mockResolvedValue({ items: [], nextCursor: null });
  });

  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    delete window.dataLayer;
    if (originalWhatsapp === undefined) {
      delete process.env.NEXT_PUBLIC_WHATSAPP_URL;
    } else {
      process.env.NEXT_PUBLIC_WHATSAPP_URL = originalWhatsapp;
    }
  });

  it('pushes view_item when the listing loads after consent', async () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    renderPage();

    await screen.findByRole('heading', { level: 1, name: 'Kowloon art' });

    await waitFor(() => {
      expect(window.dataLayer).toContainEqual({
        event: 'view_item',
        item_id: 'act-1',
        item_name: 'Kowloon art',
        item_brand: 'Studio',
        price: 180,
        currency: 'HKD',
      });
    });
  });

  it('pushes generate_lead with item fields on the WhatsApp CTA', async () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    renderPage();

    const [cta] = await screen.findAllByRole('link', { name: copy.whatsappCtaLabel });
    fireEvent.click(cta);

    expect(window.dataLayer).toContainEqual({
      event: 'generate_lead',
      lead_type: 'whatsapp_activity',
      item_id: 'act-1',
      item_name: 'Kowloon art',
      item_brand: 'Studio',
      price: 180,
      currency: 'HKD',
    });
  });

  it('does not push view_item without consent', async () => {
    renderPage();

    await screen.findByRole('heading', { level: 1, name: 'Kowloon art' });
    expect(window.dataLayer).toEqual([]);
  });

  it('shows key facts, sections, contact, rating, and the Parent-Verified badge', async () => {
    vi.mocked(fetchActivityListingById).mockResolvedValue(fullListing());
    const { container } = renderPage();

    await screen.findByRole('heading', { level: 1, name: 'Kowloon art' });
    const [facts] = screen.getAllByLabelText(copy.keyFactsLabel);
    expect(within(facts).getByText('Ages 3–6')).toBeInTheDocument();
    expect(within(facts).getByText('HK$180 / class')).toBeInTheDocument();

    for (const heading of [
      copy.aboutHeading,
      copy.scheduleHeading,
      copy.priceHeading,
      copy.locationHeading,
      copy.organiserHeading,
    ]) {
      expect(screen.getByRole('heading', { level: 2, name: heading })).toBeInTheDocument();
    }
    expect(screen.getByText('Bring an apron.')).toBeInTheDocument();
    const website = screen.getByRole('link', { name: /^Website/ });
    expect(website).toHaveAttribute('href', 'https://studio.example.com/');
    expect(website).toHaveClass('min-w-0', 'overflow-hidden');
    expect(website.closest('li')).toHaveClass('min-w-0');
    expect(screen.getByRole('link', { name: /examplestudio/ })).toHaveAttribute(
      'href',
      'https://www.instagram.com/examplestudio',
    );
    expect(screen.getByText(copy.parentVerifiedLabel)).toBeInTheDocument();
    expect(screen.getAllByText(/4\.5/).length).toBeGreaterThan(0);
    expect(container.querySelector('[data-hide-whatsapp-fab]')).not.toBeNull();
  });

  it('asks the organiser for missing facts and hides the badge without the flag', async () => {
    vi.mocked(fetchActivityListingById).mockResolvedValue(
      buildListing({ pricing: null, schedule: null }),
    );
    renderPage();

    await screen.findByRole('heading', { level: 1, name: 'Kowloon art' });
    const [facts] = screen.getAllByLabelText(copy.keyFactsLabel);
    expect(within(facts).getByRole('link', { name: copy.askForPriceLabel })).toHaveAttribute(
      'href',
      expect.stringContaining('https://wa.me/85200000000'),
    );
    expect(within(facts).getByRole('link', { name: copy.askForTimesLabel })).toBeInTheDocument();
    expect(screen.queryByText(copy.parentVerifiedLabel)).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: copy.reviewsHeading })).not.toBeInTheDocument();
  });

  it('lets visitors switch between venues', async () => {
    const first = buildListing({ location: { id: 'loc-1', address: '1 Example Road' } });
    vi.mocked(fetchActivityListingById).mockResolvedValue({
      ...first,
      variants: [
        { location: first.location, pricing: first.pricing, schedule: first.schedule },
        {
          location: buildLocation({ id: 'loc-2', address: '2 Sample Street' }),
          pricing: first.pricing,
          schedule: first.schedule,
        },
      ],
    });
    renderPage();

    await screen.findByRole('heading', { level: 1, name: 'Kowloon art' });
    expect(screen.getAllByText(formatCount(copy.locationsCountLabel, 2)).length).toBeGreaterThan(0);
    const second = screen.getByRole('button', { name: /2 Sample Street/ });
    expect(second).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(second);
    expect(second).toHaveAttribute('aria-pressed', 'true');
  });

  it('links back to the last search results', async () => {
    rememberSearchHref('/en/search?age=3-6');
    renderPage();

    await screen.findByRole('heading', { level: 1, name: 'Kowloon art' });
    expect(screen.getByRole('link', { name: copy.backToResultsLabel })).toHaveAttribute(
      'href',
      '/en/search?age=3-6',
    );
  });

  it('shows a way back when the activity is missing', async () => {
    vi.mocked(fetchActivityListingById).mockResolvedValue(null);
    renderPage();

    expect(await screen.findByText(copy.notFoundLabel)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: copy.browseActivitiesLabel })).toBeInTheDocument();
  });

  it('shows more from the organiser', async () => {
    vi.mocked(fetchActivitySearch).mockImplementation(async (params) => ({
      items: params.organizationIds
        ? [buildListing({ activity: { id: 'act-2', name: 'Clay club' } })]
        : [],
      nextCursor: null,
    }));
    renderPage();

    expect(
      await screen.findByRole('heading', { level: 2, name: copy.moreFromOrganiserHeading }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Clay club' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: copy.similarHeading })).not.toBeInTheDocument();
  });
});

function formatCount(template: string, count: number): string {
  return template.replace('{count}', String(count));
}
