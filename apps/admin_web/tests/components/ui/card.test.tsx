import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Card } from '@/components/ui/card';

describe('Card', () => {
  it('lets className replace the default border and radius', () => {
    render(
      <Card
        className='rounded-2xl border-brand-100 sm:rounded-2xl'
        data-testid='brand-card'
      >
        <p>Body</p>
      </Card>
    );

    const card = screen.getByTestId('brand-card');
    expect(card).toHaveClass('border-brand-100', 'rounded-2xl', 'sm:rounded-2xl');
    expect(card).not.toHaveClass('border-slate-200');
    expect(card).not.toHaveClass('rounded-lg');
    expect(card).not.toHaveClass('sm:rounded-xl');
    expect(screen.getByText('Body')).toBeVisible();
  });
});
