import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ActivityDetailPage } from '@/components/pages/activity-detail-page';
import { getContent } from '@/content';
import { fetchActivityListingById } from '@/lib/activities/search-client';
import type { ActivityListing } from '@/lib/activities/types';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivityListingById: vi.fn(),
}));

function buildListing(): ActivityListing {
  return {
    activity: {
      id: 'act-1',
      name: 'Kowloon art',
      description: 'Paint together',
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c1111111-1111-1111-1111-111111111101',
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

describe('ActivityDetailPage analytics', () => {
  const originalWhatsapp = process.env.NEXT_PUBLIC_WHATSAPP_URL;

  beforeEach(() => {
    window.localStorage.clear();
    window.dataLayer = [];
    process.env.NEXT_PUBLIC_WHATSAPP_URL = 'https://wa.me/85200000000';
    vi.mocked(fetchActivityListingById).mockResolvedValue(buildListing());
  });

  afterEach(() => {
    window.localStorage.clear();
    delete window.dataLayer;
    if (originalWhatsapp === undefined) {
      delete process.env.NEXT_PUBLIC_WHATSAPP_URL;
    } else {
      process.env.NEXT_PUBLIC_WHATSAPP_URL = originalWhatsapp;
    }
  });

  it('pushes view_item when the listing loads after consent', async () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    const copy = getContent('en').activityDetail;

    render(
      <ActivityDetailPage locale="en" activityId="act-1" copy={copy} />,
    );

    await screen.findByRole('heading', { name: 'Kowloon art' });

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
    const copy = getContent('en').activityDetail;

    render(
      <ActivityDetailPage locale="en" activityId="act-1" copy={copy} />,
    );

    const cta = await screen.findByRole('link', {
      name: copy.whatsappCtaLabel,
    });
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
    const copy = getContent('en').activityDetail;

    render(
      <ActivityDetailPage locale="en" activityId="act-1" copy={copy} />,
    );

    await screen.findByRole('heading', { name: 'Kowloon art' });
    expect(window.dataLayer).toEqual([]);
  });
});
