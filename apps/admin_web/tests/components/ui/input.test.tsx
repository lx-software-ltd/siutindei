import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

describe('console field primitives', () => {
  it('keeps the slate field classes when a caller passes its own', () => {
    render(<Input aria-label='Name' className='border-red-500' />);

    const input = screen.getByLabelText('Name');
    expect(input).toHaveClass('border-slate-300', 'border-red-500');
    expect(input).toHaveClass('focus:ring-slate-500');
  });

  it('keeps the slate label colour when a caller passes spacing', () => {
    render(<Label className='mb-0'>Name</Label>);

    expect(screen.getByText('Name')).toHaveClass('text-slate-700', 'mb-1', 'mb-0');
  });
});
