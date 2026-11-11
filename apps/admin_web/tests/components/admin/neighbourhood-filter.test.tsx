import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { NeighbourhoodFilter } from '@/components/admin/org-review/neighbourhood-filter';

const options = [
  { id: 'stanley', name: 'Stanley', group: 'Southern' },
  { id: 'shek-o', name: 'Shek O', group: 'Southern' },
];

describe('NeighbourhoodFilter', () => {
  it('shows a neighbourhood option by name', () => {
    render(
      <NeighbourhoodFilter
        id='review-neighbourhood-filter'
        value='stanley'
        valueName='Ignored'
        options={options}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByLabelText('Neighbourhood')).toHaveValue('Stanley');
  });

  it('shows the area name when the default is a district or region', () => {
    render(
      <NeighbourhoodFilter
        id='review-neighbourhood-filter'
        value='southern'
        valueName='Southern'
        options={options}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByLabelText('Neighbourhood')).toHaveValue('Southern');
  });
});
