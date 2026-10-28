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

  it('lets a caller replace the label spacing', () => {
    render(<Label className='mb-0'>Name</Label>);

    const label = screen.getByText('Name');
    expect(label).toHaveClass('text-ink-900', 'mb-0');
    expect(label).not.toHaveClass('mb-1', 'text-slate-700');
  });
});
