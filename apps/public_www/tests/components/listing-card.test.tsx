import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ListingCard, type ListingCardLabels } from '@/components/sections/listings/listing-card';
import { SearchProvider } from '@/components/shared/search/search-context';
import type { ActivityListing } from '@/lib/activities/types';

import { withChromeCopy } from '../helpers/chrome-copy';
import { buildListing, buildLocation, buildPricing, buildSchedule } from '../helpers/listing-fixture';

const labels: ListingCardLabels = {
  parentVerified: 'Parent-Verified',
  freeTrial: 'Free trial',
  imageFallback: 'Photo coming soon',
  locationsCount: '{count} locations',
  detailsOnRequest: 'Details on request',
};

function renderCard(listing: ActivityListing) {
  return render(
    withChromeCopy(
      <SearchProvider>
        <ListingCard locale="en" listing={listing} labels={labels} layout="grid" />
      </SearchProvider>,
    ),
  );
}

describe('ListingCard', () => {
  it('leads with the age, links once to the activity, and shows place, time, and price', () => {
    const { container } = renderCard(
      buildListing({ activity: { ageMin: 3, ageMax: 6 }, organization: { mediaUrls: [] } }),
    );

    const age = screen.getByText('Ages 3–6');
    expect(age.parentElement?.firstElementChild).toBe(age);
    expect(container.querySelector('h3')?.previousElementSibling).toBe(age.parentElement);
    const links = screen
      .getAllByRole('link')
      .filter((link) => link.getAttribute('href')?.startsWith('/en/activity'));
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAccessibleName('Kowloon art');
    expect(links[0]).toHaveAttribute('href', '/en/activity?id=act-1');
    expect(screen.getByText(/Mon 10:00–11:00/)).toBeInTheDocument();
    expect(screen.getByText('HK$180 / class')).toBeInTheDocument();
    expect(screen.queryByText(labels.parentVerified)).not.toBeInTheDocument();
  });

  it('summarises several venues and prices', () => {
    const base = buildListing();
    renderCard({
      ...base,
      variants: [
        { location: base.location, pricing: buildPricing({ amount: 220 }), schedule: buildSchedule() },
        {
          location: buildLocation({ id: 'loc-2' }),
          pricing: buildPricing({ amount: 160 }),
          schedule: buildSchedule(),
        },
      ],
    });

    expect(screen.getByText(/^2 locations/)).toBeInTheDocument();
    expect(screen.getByText('From HK$160 / class')).toBeInTheDocument();
  });

  it('shows the Parent-Verified badge only when an admin set the flag', () => {
    renderCard(buildListing({ organization: { parentVerified: true } }));

    expect(screen.getByText(labels.parentVerified)).toBeInTheDocument();
  });

  it('says details are on request without a price or schedule', () => {
    renderCard(buildListing({ pricing: null, schedule: null }));

    expect(screen.getByText(labels.detailsOnRequest)).toBeInTheDocument();
  });

  it('falls back to the category art when the photo fails', () => {
    const { container } = renderCard(
      buildListing({ organization: { mediaUrls: ['https://images.example.com/broken.jpg'] } }),
    );

    const photo = container.querySelector('img[src="https://images.example.com/broken.jpg"]');
    expect(photo).not.toBeNull();
    fireEvent.error(photo as Element);
    expect(container.querySelector('img[src="https://images.example.com/broken.jpg"]')).toBeNull();
    expect(screen.getByText(labels.imageFallback)).toBeInTheDocument();
  });
});
