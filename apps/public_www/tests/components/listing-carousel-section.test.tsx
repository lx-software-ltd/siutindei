import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ListingCarouselSection } from '@/components/sections/listings/listing-carousel-section';
import { SearchProvider } from '@/components/shared/search/search-context';

import { withChromeCopy } from '../helpers/chrome-copy';
import { buildListing } from '../helpers/listing-fixture';

const labels = {
  parentVerified: 'Parent-Verified',
  freeTrial: 'Free trial',
  imageFallback: 'Photo coming soon',
  locationsCount: '{count} locations',
  detailsOnRequest: 'Details on request',
  previous: 'Previous',
  next: 'Next',
};

describe('ListingCarouselSection', () => {
  it('links the title and right-circle arrow to the search href', () => {
    render(
      <SearchProvider>
        <ListingCarouselSection
          locale="en"
          title="Activities in Kowloon"
          searchHref="/en/search/?age=3-6&region=kowloon"
          seeAllLabel="See all"
          listings={[]}
          isLoading={false}
          labels={labels}
        />
      </SearchProvider>,
    );

    const titleLink = screen.getByRole('link', {
      name: 'Activities in Kowloon',
    });
    const seeAllLink = screen.getByRole('link', {
      name: 'See all: Activities in Kowloon',
    });

    expect(titleLink).toHaveAttribute(
      'href',
      '/en/search?age=3-6&region=kowloon',
    );
    expect(seeAllLink).toHaveAttribute(
      'href',
      '/en/search?age=3-6&region=kowloon',
    );
    expect(seeAllLink).toHaveClass('link-unadorned');
    expect(seeAllLink.querySelector('img')).toHaveAttribute(
      'src',
      '/images/ui/chevron-right.svg',
    );
    expect(
      screen.getAllByRole('button').map((button) => button.getAttribute('aria-label')),
    ).toEqual(['Previous', 'Next']);
  });

  it('does not render a map under homepage carousel cards', () => {
    const { container } = render(
      withChromeCopy(
        <SearchProvider>
          <ListingCarouselSection
            locale="en"
            title="Popular activities in Stanley"
            searchHref="/en/search/?region=stanley"
            seeAllLabel="See all"
            listings={[buildListing()]}
            isLoading={false}
            isPrimaryCarousel
            labels={labels}
          />
        </SearchProvider>,
      ),
    );

    expect(screen.getByRole('link', { name: 'Kowloon art' })).toBeInTheDocument();
    expect(container.querySelector('.listing-card-mini-map')).toBeNull();
    expect(container.querySelector('img[src*="staticmap"]')).toBeNull();
  });
});
