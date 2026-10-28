import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

describe('console field primitives', () => {
  it('uses the brand field and lets a caller border replace it', () => {
    render(<Input aria-label='Name' className='border-red-500' />);

    const input = screen.getByLabelText('Name');
    expect(input).toHaveClass('border-red-500', 'focus:ring-brand-700', 'text-ink-900');
    expect(input).not.toHaveClass('border-ink-900/15');
  });

  it('keeps the default label margin when a caller also passes one', () => {
    render(<Label className='mb-0'>Name</Label>);

    const label = screen.getByText('Name');
    expect(label).toHaveClass('text-ink-900', 'mb-1');
    expect(label).not.toHaveClass('text-slate-700');
  });
});
