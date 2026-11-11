import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ListingGrid } from '@/components/sections/listings/listing-grid';

describe('ListingGrid', () => {
  it('uses a shrinkable single column on phones so long card text cannot widen the page', () => {
    const { container } = render(
      <ListingGrid
        locale="en"
        listings={[]}
        isLoading
        labels={{ empty: 'No activities' } as never}
      />,
    );

    expect(container.querySelector('.listing-grid')).toHaveClass(
      'grid-cols-1',
      'sm:grid-cols-3',
    );
  });
});
