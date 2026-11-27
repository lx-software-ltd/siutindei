import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SearchMapListItem } from '@/components/sections/search/search-map-list-item';

import { buildListing } from '../helpers/listing-fixture';

const labels = {
  imageFallback: 'Photo coming soon',
  view: 'View',
  locationsCount: '{count} locations',
  detailsOnRequest: 'Details on request',
};

describe('SearchMapListItem', () => {
  it('covers the thumbnail and contains a logo', () => {
    const photo = render(
      <SearchMapListItem
        kind="summary"
        locale="en"
        listing={buildListing({
          organization: { mediaUrls: ['https://images.example.com/wide.jpg'] },
        })}
        labels={labels}
      />,
    );
    expect(photo.container.querySelector('img[src="https://images.example.com/wide.jpg"]')).toHaveClass(
      'absolute',
      'inset-0',
      'h-full',
      'w-full',
      'object-cover',
    );
    photo.unmount();

    const logo = render(
      <SearchMapListItem
        kind="summary"
        locale="en"
        listing={buildListing({
          organization: { mediaUrls: [], logoMediaUrl: 'https://images.example.com/logo.png' },
        })}
        labels={labels}
      />,
    );
    expect(logo.container.querySelector('img[src="https://images.example.com/logo.png"]')).toHaveClass(
      'absolute',
      'inset-0',
      'object-contain',
    );
  });
});
